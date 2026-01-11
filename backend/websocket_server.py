import asyncio
import json
import logging
from aiohttp import web
import websockets

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# WebSocket server settings
WS_HOST = "localhost"
WS_PORT = 8080
HTTP_PORT = 8081  # Internal HTTP port for receiving notifications from Flask


class DocumentConnectionManager:
    """
    Manages WebSocket connections and document subscriptions.
    
    Clients can subscribe to specific document IDs and will receive
    notifications when those documents are updated.
    """
    
    def __init__(self):
        self.subscriptions: dict[str, set] = {}
        self.client_subscriptions: dict = {}
        self.clients: set = set()
    
    def connect(self, websocket):
        """Register a new client connection."""
        self.clients.add(websocket)
        self.client_subscriptions[websocket] = set()
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
    
    def disconnect(self, websocket):
        """Clean up when a client disconnects."""
        # Remove from all document subscriptions
        if websocket in self.client_subscriptions:
            for doc_id in self.client_subscriptions[websocket]:
                if doc_id in self.subscriptions:
                    self.subscriptions[doc_id].discard(websocket)
                    # Clean up empty subscription sets
                    if not self.subscriptions[doc_id]:
                        del self.subscriptions[doc_id]
            del self.client_subscriptions[websocket]
        
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
    
    def subscribe(self, websocket, doc_id: str):
        """Subscribe a client to receive updates for a specific document."""
        if doc_id not in self.subscriptions:
            self.subscriptions[doc_id] = set()
        
        self.subscriptions[doc_id].add(websocket)
        self.client_subscriptions[websocket].add(doc_id)
        logger.info(f"Client subscribed to document: {doc_id}")
    
    def unsubscribe(self, websocket, doc_id: str):
        """Unsubscribe a client from a specific document."""
        if doc_id in self.subscriptions:
            self.subscriptions[doc_id].discard(websocket)
            if not self.subscriptions[doc_id]:
                del self.subscriptions[doc_id]
        
        if websocket in self.client_subscriptions:
            self.client_subscriptions[websocket].discard(doc_id)
        logger.info(f"Client unsubscribed from document: {doc_id}")
    
    async def broadcast_to_document(self, doc_id: str, message: dict):
        """Send a message to all clients subscribed to a document."""
        if doc_id not in self.subscriptions:
            logger.info(f"No subscribers for document: {doc_id}")
            return
        
        subscribers = self.subscriptions[doc_id].copy()
        if not subscribers:
            return
        
        message_json = json.dumps(message)
        logger.info(f"Broadcasting to {len(subscribers)} subscribers of document: {doc_id}")
        
        # Send to all subscribers
        disconnected = set()
        for websocket in subscribers:
            try:
                await websocket.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(websocket)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)


# Global connection manager
manager = DocumentConnectionManager()


async def websocket_handler(websocket):
    """
    Handle incoming WebSocket connections from frontend clients.
    
    Expected message format:
    {
        "action": "subscribe" | "unsubscribe",
        "doc_id": "document-uuid"
    }
    """
    manager.connect(websocket)
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action")
                doc_id = data.get("doc_id")
                
                if not action or not doc_id:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Missing 'action' or 'doc_id'"
                    }))
                    continue
                
                if action == "subscribe":
                    manager.subscribe(websocket, doc_id)
                    await websocket.send(json.dumps({
                        "type": "subscribed",
                        "doc_id": doc_id
                    }))
                
                elif action == "unsubscribe":
                    manager.unsubscribe(websocket, doc_id)
                    await websocket.send(json.dumps({
                        "type": "unsubscribed",
                        "doc_id": doc_id
                    }))
                
                else:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        manager.disconnect(websocket)


async def handle_notify(request):
    """
    HTTP endpoint to receive notifications from Flask API.
    
    Expected POST body:
    {
        "doc_id": "document-uuid",
        "action": "insert" | "delete" | "update"
    }
    """
    try:
        data = await request.json()
        doc_id = data.get("doc_id")
        action = data.get("action", "update")
        
        if not doc_id:
            return web.json_response(
                {"error": "Missing doc_id"},
                status=400
            )
        
        # Broadcast to all subscribers of this document
        await manager.broadcast_to_document(doc_id, {
            "type": "document_update",
            "doc_id": doc_id,
            "action": action
        })
        
        return web.json_response({"status": "ok"})
    
    except Exception as e:
        logger.error(f"Error handling notification: {e}")
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def handle_health(request):
    """Health check endpoint."""
    return web.json_response({
        "status": "healthy",
        "clients": len(manager.clients),
        "subscriptions": {k: len(v) for k, v in manager.subscriptions.items()}
    })


async def start_http_server():
    """Start the internal HTTP server for receiving notifications."""
    app = web.Application()
    app.router.add_post("/notify", handle_notify)
    app.router.add_get("/health", handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", HTTP_PORT)
    await site.start()
    logger.info(f"HTTP notification server started on http://localhost:{HTTP_PORT}")
    return runner


async def main():
    """Main entry point - starts both WebSocket and HTTP servers."""
    logger.info("Starting Document WebSocket Server...")
    
    # Start the HTTP server for receiving notifications from Flask
    http_runner = await start_http_server()
    
    # Start the WebSocket server for frontend clients
    async with websockets.serve(websocket_handler, WS_HOST, WS_PORT):
        logger.info(f"WebSocket server started on ws://{WS_HOST}:{WS_PORT}")
        logger.info("Ready to accept connections!")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
