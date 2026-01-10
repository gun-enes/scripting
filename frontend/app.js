// --- CONFIGURATION ---
const API_BASE = "http://localhost:8000/api/document";
const WS_URL = "ws://localhost:8080"; 

let socket = null;
let currentDocId = null;

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
    };

    socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        console.log("WS Notification:", msg);

        // LOGIC: If the current document was updated by someone else, reload it.
        // Expecting format: {"status": "success", "value": {"obj": "DOC_ID_HERE", "method": "update"}}
        // Or simply: {"type": "update", "doc_id": "..."} depending on your WS implementation.
        
        // Adjust this condition based on your exact WS message structure
        if (msg.value && msg.value.obj === currentDocId) {
            console.log("Concurrent update detected! Refreshing view...");
            loadCurrentDoc(); // <--- This creates the "real-time" feel
        }
    };
}

// --- 2. REST API ACTIONS ---
function refreshDocList() {
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
    });
}

function loadCurrentDocWithPath() {
    loadCurrentDoc();
}

function loadCurrentDoc() {
    currentDocId = $('#docSelector').val();
    if (!currentDocId) return;

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
