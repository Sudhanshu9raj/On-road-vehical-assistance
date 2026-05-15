// Leaflet Map Setup
let map, userMarker, mechanicMarker, otherMarkers = {};
let activeRequestId = null;
const socket = io();

function initMap(lat, lng) {
    console.log(`[DEBUG] Initializing map at ${lat}, ${lng}`);
    map = L.map('map').setView([lat, lng], 15);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    const userLabel = USER_ROLE === 'user' ? "You are here" : "Your Location";
    userMarker = L.marker([lat, lng]).addTo(map).bindPopup(userLabel).openPopup();
    console.log(`[DEBUG] ${userLabel} marker added`);
    
    // Fix map rendering issues
    setTimeout(() => {
        map.invalidateSize();
        console.log("[DEBUG] Map size invalidated");
    }, 300);
}

// Geolocation
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(position => {
        const { latitude, longitude } = position.coords;
        initMap(latitude, longitude);
        
        // Start reporting location to server
        setInterval(() => {
            socket.emit('update_location', { lat: latitude, lng: longitude });
        }, 5000);
    }, error => {
        console.error("Error getting location", error);
        initMap(20.5937, 78.9629); // Default center (India)
    });
}

// Socket Events
socket.on('connect', () => {
    socket.emit('join', { room: `user_${USER_ID}` });
    console.log("[DEBUG] Connected to Socket.IO");
});

socket.on('location_update', data => {
    console.log(`[DEBUG] Location received for ${data.role}: ${data.lat}, ${data.lng}`);
    if (data.role === 'mechanic' && USER_ROLE === 'user') {
        if (!mechanicMarker) {
            mechanicMarker = L.marker([data.lat, data.lng], {
                icon: L.icon({
                    iconUrl: 'https://cdn-icons-png.flaticon.com/512/1995/1995429.png',
                    iconSize: [32, 32]
                })
            }).addTo(map).bindPopup("Mechanic Location");
            console.log("[DEBUG] Mechanic marker added to User map");
        } else {
            mechanicMarker.setLatLng([data.lat, data.lng]);
            console.log("[DEBUG] Mechanic marker updated on User map");
        }
    } else if (data.role === 'user' && USER_ROLE === 'mechanic') {
        if (activeRequestId) {
            if (!otherMarkers['active_user']) {
                otherMarkers['active_user'] = L.marker([data.lat, data.lng]).addTo(map).bindPopup("User Location");
                console.log("[DEBUG] User marker added to Mechanic map");
            } else {
                otherMarkers['active_user'].setLatLng([data.lat, data.lng]);
                console.log("[DEBUG] User marker updated on Mechanic map");
            }
        }
    }
});

socket.on('new_request', data => {
    if (USER_ROLE === 'mechanic' && !activeRequestId) {
        addNearbyRequest(data);
    }
});

socket.on('request_accepted', data => {
    if (USER_ROLE === 'user') {
        activeRequestId = data.request_id;
        showActiveRequest(data);
    }
});

socket.on('status_updated', data => {
    const statusEl = document.getElementById(USER_ROLE === 'user' ? 'active-status' : 'task-status');
    if (statusEl) {
        statusEl.innerText = data.status.replace('_', ' ');
        statusEl.className = `status-badge status-${data.status}`;
    }
    if (data.status === 'completed' || data.status === 'rejected') {
        setTimeout(() => location.reload(), 3000);
    }
});

socket.on('receive_message', data => {
    appendMessage(data);
});

// UI Logic - User Dashboard
const btnRequest = document.getElementById('btn-request');
if (btnRequest) {
    btnRequest.onclick = () => {
        const issueType = document.getElementById('issue-type').value;
        const pos = userMarker.getLatLng();
        
        fetch('/api/requests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ issue_type: issueType, lat: pos.lat, lng: pos.lng })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                activeRequestId = data.request_id;
                document.getElementById('request-form-section').style.display = 'none';
                document.getElementById('active-request-section').style.display = 'block';
                document.getElementById('active-issue-title').innerText = issueType;
                socket.emit('join', { room: `request_${data.request_id}` });
                loadHistory();
            }
        });
    };
}

const btnDeleteReq = document.getElementById('btn-delete-request');
if (btnDeleteReq) {
    btnDeleteReq.onclick = () => {
        if (confirm("Are you sure you want to cancel this request?")) {
            fetch(`/api/requests/${activeRequestId}/delete`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') location.reload();
            });
        }
    };
}

function showActiveRequest(data) {
    document.getElementById('mechanic-info').innerText = `Mechanic: ${data.mechanic_name} is coming!`;
    document.getElementById('chat-box').style.display = 'flex';
    socket.emit('join', { room: `request_${data.request_id}` });
}

// UI Logic - Mechanic Dashboard
function addNearbyRequest(req) {
    const list = document.getElementById('nearby-list');
    const div = document.createElement('div');
    div.className = 'glass-card';
    div.style.padding = '1rem';
    div.id = `nearby-req-${req.id}`;
    div.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <strong style="color: var(--accent-blue);">${req.issue_type}</strong><br>
                <span style="font-size: 0.8rem; color: var(--text-dim);">By: ${req.username}</span>
            </div>
            <button class="btn-glow" onclick="acceptRequest(${req.id})" style="padding: 5px 15px; font-size: 0.8rem;">Accept</button>
        </div>
    `;
    list.appendChild(div);

    // Add marker on map
    otherMarkers[req.id] = L.marker([req.lat, req.lng], {
        icon: L.icon({
            iconUrl: 'https://cdn-icons-png.flaticon.com/512/3208/3208707.png',
            iconSize: [32, 32]
        })
    }).addTo(map).bindPopup(`${req.issue_type} by ${req.username}`);
}

window.acceptRequest = (id) => {
    socket.emit('accept_request', { request_id: id });
    activeRequestId = id;
    document.getElementById('nearby-section').style.display = 'none';
    document.getElementById('active-task-section').style.display = 'block';
    document.getElementById('availability-status').innerText = '● Busy with active task';
    document.getElementById('availability-status').style.color = 'var(--status-rejected)';
    socket.emit('join', { room: `request_${id}` });
};

const statusSelect = document.getElementById('status-update-select');
if (statusSelect) {
    statusSelect.onchange = () => {
        socket.emit('update_status', { request_id: activeRequestId, status: statusSelect.value });
    };
}

// Chat Logic
const msgInput = document.getElementById('chat-msg-input');
const btnSend = document.getElementById('btn-chat-send');

if (btnSend) {
    btnSend.onclick = sendMessage;
    msgInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };
}

function sendMessage() {
    const msg = msgInput.value.trim();
    if (msg && activeRequestId) {
        socket.emit('send_message', { request_id: activeRequestId, message: msg });
        msgInput.value = '';
    }
}

function appendMessage(data) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `message ${data.sender_id === USER_ID ? 'sent' : 'received'}`;
    div.innerHTML = `
        <div style="font-size: 0.7rem; opacity: 0.7;">${data.sender_name}</div>
        <div>${data.message}</div>
        <div style="font-size: 0.6rem; text-align: right; opacity: 0.5;">${data.timestamp}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// History
function loadHistory() {
    const list = document.getElementById('history-list');
    if (!list) return;

    fetch('/api/requests/history')
    .then(res => res.json())
    .then(data => {
        list.innerHTML = '';
        data.forEach(req => {
            const div = document.createElement('div');
            div.style.padding = '10px';
            div.style.borderBottom = '1px solid var(--glass-border)';
            div.innerHTML = `
                <div style="display: flex; justify-content: space-between; font-size: 0.9rem;">
                    <strong>${req.issue_type}</strong>
                    <span class="status-badge status-${req.status}" style="font-size: 0.6rem;">${req.status}</span>
                </div>
                <div style="font-size: 0.7rem; color: var(--text-dim);">
                    ${req.created_at} | ${USER_ROLE === 'user' ? 'Mech: ' + req.mechanic : 'User: ' + req.user}
                </div>
            `;
            list.appendChild(div);
        });
    });
}

loadHistory();
setInterval(loadHistory, 30000);
