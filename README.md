# Collaborative Text Editor

## Project Selection
Collaborative Text Editor

## Project Members

| Name | Student ID |
|------|------------|
| Berat Türk | 2581098 |
| Enes Gün | 2521631 |

## Project Description

A real-time collaborative document editing system that allows multiple users to view and edit documents simultaneously. The application features a tree-based document structure where documents can contain nested elements (paragraphs, lists, tables, etc.) and supports real-time synchronization via WebSocket push notifications.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Browser)                        │
│  - REST API calls for CRUD operations                       │
│  - WebSocket connection for real-time updates               │
└─────────────────────────────────────────────────────────────┘
                    │                       │
                    ▼                       ▼
        ┌───────────────────┐    ┌─────────────────────┐
        │   Flask API       │    │  WebSocket Server   │
        │   (Port 8000)     │───▶│  (Port 8080/8081)   │
        └───────────────────┘    └─────────────────────┘
                    │
                    ▼
        ┌───────────────────┐
        │   SQLite DB       │
        │  (document.db)    │
        └───────────────────┘
```

## File Structure

### Backend (`/backend`)

| File | Description |
|------|-------------|
| `api.py` | Flask REST API server. Handles all HTTP endpoints for document operations (create, read, update, delete, search, import). Sends notifications to WebSocket server on changes. |
| `websocket_server.py` | Asyncio-based WebSocket server. Manages client connections, document subscriptions, and broadcasts real-time update notifications to connected clients. |
| `document.py` | Document class representing a node in the document tree. Supports nested children, markup types (paragraph, list, table, etc.), and attributes. Includes HTML rendering and JSON serialization. |
| `new_db.py` | Database layer using SQLite. Handles persistence of the document tree structure with path-based indexing for efficient subtree queries. |
| `repo.py` | Repository pattern wrapper for document operations. Manages in-memory document cache and database interactions. |
| `document.db` | SQLite database file storing all documents. |

### Frontend (`/frontend`)

| File | Description |
|------|-------------|
| `index.html` | Main HTML page with the document editor UI. Features a sidebar with controls and a split main view showing visual preview and JSON structure. |
| `app.js` | JavaScript application logic. Handles REST API calls, WebSocket connection management, document subscriptions, and UI updates. |
| `style.css` | Stylesheet for the application (styles are embedded in index.html). |

## How to Run

### 1. Start the WebSocket Server
```bash
cd backend
python3 websocket_server.py
```

### 2. Start the Flask API Server
```bash
cd backend
python3 api.py
```

### 3. Serve the Frontend
```bash
cd frontend
python3 -m http.server 8080
```

### 4. Open the Application
Navigate to: http://localhost:8080

## Features

- **Document Tree Structure**: Documents are hierarchical with support for nested elements
- **Real-time Collaboration**: WebSocket-based push notifications for instant updates
- **Multiple Markup Types**: Support for paragraph, text, strong, list, item, table, row, cell, image
- **Visual Preview**: HTML rendering of the document structure
- **JSON View**: Raw JSON structure display for debugging
- **Search**: Full-text search within documents
- **Import/Export**: JSON import functionality for creating documents from templates

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/document` | List all documents |
| POST | `/api/document` | Create new empty document |
| GET | `/api/document/<id>` | Get document by ID |
| POST | `/api/document/<id>/insert` | Insert content at path |
| DELETE | `/api/document/<id>/delete` | Delete content at path |
| GET | `/api/document/<id>/search` | Search within document |
| GET | `/api/document/<id>/draw` | Get HTML rendering |
| POST | `/api/document/import` | Import JSON document |
