// --- CONFIGURATION ---
const API_BASE = "http://localhost:8000/api/document";
const WS_URL = "ws://localhost:8080"; 

let socket = null;
let currentDocId = null;
let subscribedDocId = null;  // Track which document we're subscribed to

$(document).ready(() => {
    refreshDocList();
    initWebSocket();
});

// --- 1. WEBSOCKET SETUP ---
function initWebSocket() {
    socket = new WebSocket(WS_URL);
    
    socket.onopen = () => {
        $('#wsStatus').text("Online").attr('class', 'online');
    };
    
    socket.onclose = () => {
        $('#wsStatus').text("Offline").attr('class', 'offline');
        subscribedDocId = null;  // Reset subscription on disconnect
        
        // Attempt to reconnect after 3 seconds
        setTimeout(() => {
            console.log("Attempting to reconnect...");
            initWebSocket();
        }, 3000);
    };

    socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        console.log("WS Notification:", msg);

        // Handle different message types
        if (msg.type === "subscribed") {
            console.log(`Successfully subscribed to document: ${msg.doc_id}`);
            return;
        }
        
        if (msg.type === "unsubscribed") {
            console.log(`Unsubscribed from document: ${msg.doc_id}`);
            return;
        }
        
        if (msg.type === "error") {
            console.error("WebSocket error:", msg.message);
            return;
        }

        // Handle document update notifications
        if (msg.type === "document_update" && msg.doc_id === currentDocId) {
            console.log(`Document ${msg.doc_id} was updated (${msg.action}). Reloading...`);
            loadCurrentDoc();
        }
    };
}

// --- 2. REST API ACTIONS ---
function refreshDocList() {
    // Save current selection before refreshing
    const previousSelection = $('#docSelector').val();
    
    $.get(API_BASE, (response) => {
        // response.value looks like: [ ["uuid-1"], ["uuid-2"] ]
        const list = response.value || []; 
        const sel = $('#docSelector');
        sel.empty().append('<option disabled selected>-- Select --</option>');
        
        list.forEach(item => {
            // item is an array like ["4e16c37a..."]
            // We need the first element (index 0)
            let id = item[0]; 
            
            // Only add if ID exists
            if (id) {
                sel.append(`<option value="${id}">${id}</option>`);
            }
        });
        
        // Restore previous selection if it still exists in the list
        if (previousSelection && sel.find(`option[value="${previousSelection}"]`).length > 0) {
            sel.val(previousSelection);
        }
    });
}

function loadCurrentDocWithPath() {
    loadCurrentDoc();
}

function loadCurrentDoc() {
    // Get the selected doc from dropdown, or use existing currentDocId
    const selectedDoc = $('#docSelector').val();
    
    // If there's a valid selection from dropdown, use it
    if (selectedDoc && selectedDoc !== '-- Select --') {
        currentDocId = selectedDoc;
    }
    
    // If no document selected, return early
    if (!currentDocId) return;
    
    // Ensure the dropdown shows the correct selection
    if ($('#docSelector').val() !== currentDocId) {
        $('#docSelector').val(currentDocId);
    }

    // Subscribe to this document for real-time updates
    subscribeToDocument(currentDocId);

    // 1. Get the path from the input box
    const pathVal = $('#targetPath').val().trim();
    
    // 2. Construct Query String (e.g., "?path=0/1")
    const queryParams = pathVal ? `?path=${encodeURIComponent(pathVal)}` : "";

    console.log(`Loading doc: ${currentDocId}, Path: ${pathVal}`);

    // 3. Request VISUAL (HTML) with path
    $.get(`${API_BASE}/${currentDocId}/draw${queryParams}`, (htmlContent) => {
        $('#visual-content').html(htmlContent);
    }).fail((err) => {
        $('#visual-content').html(`<p style="color:red">Error: ${err.responseText || err.statusText}</p>`);
    });

    // 4. Request DATA (JSON) with path
    $.get(`${API_BASE}/${currentDocId}${queryParams}`, (response) => {
        // Handle wrapping if your backend returns {"result":..., "value":...}
        const data = response.value || response;
        const prettyJson = JSON.stringify(data, null, 4);
        $('#json-content').text(prettyJson);
    }).fail((err) => {
        $('#json-content').text(`Error loading JSON: ${err.responseText || err.statusText}`);
    });
}

// Subscribe to a document for real-time updates
function subscribeToDocument(docId) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.warn("WebSocket not connected. Cannot subscribe.");
        return;
    }
    
    // Unsubscribe from previous document if different
    if (subscribedDocId && subscribedDocId !== docId) {
        socket.send(JSON.stringify({
            action: "unsubscribe",
            doc_id: subscribedDocId
        }));
    }
    
    // Subscribe to new document
    socket.send(JSON.stringify({
        action: "subscribe",
        doc_id: docId
    }));
    
    subscribedDocId = docId;
}

function createNewDoc() {
    $.post(API_BASE, {}, (res) => {
        alert("Created: " + res.value);
        refreshDocList();
    });
}

function performInsert() {
    if (!currentDocId) return alert("Select a document first");
    
    const path = $('#targetPath').val();
    const rawPayload = $('#payload').val();
    
    if (!path) return alert("Path is required");

    let jsonData;
    try {
        // Try parsing JSON. If it fails, assume it's a simple string value wrapped in dict
        jsonData = JSON.parse(rawPayload);
    } catch (e) {
        // If user typed "Hello", treat it as {"value": "Hello"}
        jsonData = { "value": rawPayload };
    }

    $.ajax({
        url: `${API_BASE}/${currentDocId}/insert?path=${path}`,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(jsonData),
        success: (res) => {
            console.log("Insert success:", res);
            // We reload immediately for ourselves. 
            // The WS server will tell *others* to reload.
            loadCurrentDoc(); 
        },
        error: (err) => alert("Error: " + JSON.stringify(err.responseJSON))
    });
}

// Quick Edit: Create element with markup or set content value
function performQuickEdit() {
    if (!currentDocId) return alert("Select a document first");
    
    const path = $('#quickEditPath').val().trim();
    const value = $('#quickEditValue').val().trim();
    
    if (!path) return alert("Path is required");
    if (!value) return alert("Value is required");
    
    // List of known markup types
    const markupTypes = [
        'document', 'paragraph', 'strong', 'text', 'list',
        'item', 'table', 'row', 'cell', 'image'
    ];
    
    let payload;
    
    // Check if the value is a markup type (create new element)
    if (markupTypes.includes(value.toLowerCase())) {
        // Create an element with this markup type
        payload = { "markup": value.toLowerCase() };
    } else {
        // Treat as content value
        payload = { "value": value };
    }
    
    $.ajax({
        url: `${API_BASE}/${currentDocId}/insert?path=${encodeURIComponent(path)}`,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        success: (res) => {
            console.log("Quick Edit success:", res);
            loadCurrentDoc();
            // Clear inputs after success
            $('#quickEditPath').val('');
            $('#quickEditValue').val('');
        },
        error: (err) => {
            const reason = err.responseJSON ? err.responseJSON.reason : err.statusText;
            alert("Quick Edit Failed: " + reason);
        }
    });
}

function performImport() {
    const rawJson = $('#importPayload').val();
    if (!rawJson) return alert("Please paste JSON data first");

    let payload;
    try {
        payload = JSON.parse(rawJson);
    } catch (e) {
        return alert("Invalid JSON syntax. Please check your input.");
    }

    // Send to /api/document/import
    $.ajax({
        url: `${API_BASE}/import`,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        success: (res) => {
            // res.value contains the new Document ID (from your backend logic)
            alert("Import Successful! New ID: " + res.value);
            
            // Clear the textarea
            $('#importPayload').val('');
            
            // Refresh the dropdown list so the user can select the new document immediately
            refreshDocList();
        },
        error: (err) => {
            const reason = err.responseJSON ? err.responseJSON.reason : err.statusText;
            alert("Import Failed: " + reason);
        }
    });
}

function performDelete() {
    if (!currentDocId) return alert("Select a document first");
    const pathVal = $('#deletePath').val().trim();
    
    $.ajax({
        url: `${API_BASE}/${currentDocId}/delete?path=${encodeURIComponent(pathVal)}`,
        type: 'DELETE',
        success: (res) => {
            console.log("Delete success:", res);
            loadCurrentDoc();
        }
    });
}

function performSearch() {
    if (!currentDocId) return;
    const q = $('#searchQ').val();
    
    $.get(`${API_BASE}/${currentDocId}/search?q=${q}`, (res) => {
        $('#searchResults').text(JSON.stringify(res.value));
    });
}
