from flask import Flask, render_template_string, request, session, redirect, url_for, send_file
from flask_socketio import SocketIO, emit, disconnect
import json
import subprocess
import os
import base64
import time
import io
from PIL import Image

app = Flask(__name__)
app.config['SECRET_KEY'] = 'WEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE@!!!!##########@'
socketio = SocketIO(app, cors_allowed_origins="*")

# Hardcoded password
ADMIN_PASSWORD = "AEae123@"

# Store local client connection
local_client_sid = None
local_connected = False

# Store screenshots temporarily (for 20 minutes)
screenshots = {}

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Enhanced Remote Terminal</title>
    <style>
        body {
            background: #1e1e1e;
            color: #ffffff;
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .tabs {
            display: flex;
            background: #2d2d2d;
            border-radius: 5px;
            overflow: hidden;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            background: #3d3d3d;
            border: none;
            color: white;
            transition: background 0.3s;
        }
        .tab.active {
            background: #007acc;
        }
        .tab:hover {
            background: #4d4d4d;
        }
        .tab-content {
            display: none;
            background: #2d2d2d;
            border-radius: 5px;
            padding: 20px;
            margin-top: 20px;
        }
        .tab-content.active {
            display: block;
        }
        .status {
            background: #2d2d2d;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
        }
        .connected {
            color: #00ff00;
        }
        .disconnected {
            color: #ff4444;
        }
        .terminal {
            background: #000000;
            border: 2px solid #333;
            border-radius: 5px;
            padding: 20px;
            height: 500px;
            overflow-y: auto;
            font-size: 14px;
            line-height: 1.4;
        }
        .prompt {
            color: #00ff00;
            margin-top: 10px;
        }
        .output {
            color: #ffffff;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .error {
            color: #ff4444;
        }
        .input-container {
            margin-top: 20px;
            display: flex;
        }
        .command-input {
            flex: 1;
            background: #2d2d2d;
            border: 1px solid #555;
            color: #ffffff;
            padding: 10px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
        }
        .btn {
            background: #007acc;
            border: none;
            color: white;
            padding: 10px 20px;
            cursor: pointer;
            font-family: 'Courier New', monospace;
            margin-left: 10px;
            border-radius: 3px;
        }
        .btn:hover {
            background: #005a9e;
        }
        .btn-danger {
            background: #dc3545;
        }
        .btn-danger:hover {
            background: #c82333;
        }
        .btn-success {
            background: #28a745;
        }
        .btn-success:hover {
            background: #218838;
        }
        .monitor-container {
            position: relative;
            background: #000;
            border: 2px solid #333;
            border-radius: 5px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 400px;
        }
        .screen {
            max-width: 100%;
            max-height: 600px;
            cursor: crosshair;
        }
        .control-buttons {
            margin: 20px 0;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .processes-table {
            background: #333;
            border-radius: 5px;
            overflow: hidden;
            margin-top: 20px;
        }
        .process-row {
            display: flex;
            padding: 10px;
            border-bottom: 1px solid #555;
            align-items: center;
        }
        .process-row:hover {
            background: #404040;
        }
        .process-info {
            flex: 1;
            display: flex;
            gap: 20px;
        }
        .process-actions {
            display: flex;
            gap: 10px;
        }
        .screenshot-gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .screenshot-item {
            background: #333;
            border-radius: 5px;
            padding: 15px;
            text-align: center;
        }
        .screenshot-thumb {
            max-width: 100%;
            height: 200px;
            object-fit: contain;
            border-radius: 3px;
            cursor: pointer;
        }
        .login-form {
            max-width: 400px;
            margin: 100px auto;
            background: #2d2d2d;
            padding: 40px;
            border-radius: 10px;
            text-align: center;
        }
        .login-input {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            background: #1e1e1e;
            border: 1px solid #555;
            color: #ffffff;
            border-radius: 5px;
        }
        .login-btn {
            background: #007acc;
            border: none;
            color: white;
            padding: 10px 20px;
            cursor: pointer;
            border-radius: 5px;
            width: 100%;
        }
        #liveMonitorStatus {
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 12px;
        }
        .monitor-off {
            background: #dc3545;
        }
        .monitor-on {
            background: #28a745;
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.4/socket.io.js"></script>
</head>
<body>
    {% if not authenticated %}
    <div class="login-form">
        <h2>Enhanced Remote Terminal Access</h2>
        <form method="POST">
            <input type="password" name="password" placeholder="Enter password" class="login-input" required>
            <button type="submit" class="login-btn">Login</button>
        </form>
        {% if error %}
        <p style="color: #ff4444; margin-top: 20px;">{{ error }}</p>
        {% endif %}
    </div>
    {% else %}
    <div class="container">
        <div class="header">
            <h1>Enhanced Remote Terminal</h1>
            <div class="status">
                Local PC Status: <span id="status" class="disconnected">Disconnected</span>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <div class="tabs">
            <button class="tab active" onclick="showTab('terminal')">Terminal</button>
            <button class="tab" onclick="showTab('monitor')">Live Monitor</button>
            <button class="tab" onclick="showTab('screenshots')">Screenshots</button>
            <button class="tab" onclick="showTab('processes')">Processes</button>
        </div>

        <!-- Terminal Tab -->
        <div id="terminal" class="tab-content active">
            <div class="terminal" id="terminalOutput">
                <div class="output">Welcome to Enhanced Remote Terminal</div>
                <div class="output">Connecting to local PC...</div>
            </div>
            <div class="input-container">
                <input type="text" id="commandInput" class="command-input" placeholder="Enter command..." autocomplete="off">
                <button onclick="sendCommand()" class="btn">Send</button>
                <button onclick="sendCtrlC()" class="btn btn-danger">Ctrl+C</button>
            </div>
        </div>

        <!-- Live Monitor Tab -->
        <div id="monitor" class="tab-content">
            <div class="control-buttons">
                <button onclick="startLiveMonitor()" class="btn btn-success">Start Live Monitor</button>
                <button onclick="stopLiveMonitor()" class="btn btn-danger">Stop Live Monitor</button>
                <span id="liveMonitorStatus" class="monitor-off">Monitor: OFF</span>
            </div>
            <div class="monitor-container">
                <img id="liveScreen" class="screen" style="display: none;" alt="Live Screen">
                <div id="monitorPlaceholder">Live monitor will appear here</div>
            </div>
        </div>

        <!-- Screenshots Tab -->
        <div id="screenshots" class="tab-content">
            <div class="control-buttons">
                <button onclick="takeScreenshot()" class="btn">Take Screenshot</button>
                <button onclick="refreshScreenshots()" class="btn">Refresh</button>
            </div>
            <div id="screenshotGallery" class="screenshot-gallery">
                <!-- Screenshots will be populated here -->
            </div>
        </div>

        <!-- Processes Tab -->
        <div id="processes" class="tab-content">
            <div class="control-buttons">
                <button onclick="refreshProcesses()" class="btn">Refresh Processes</button>
            </div>
            <div id="processList" class="processes-table">
                <!-- Processes will be populated here -->
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        let liveMonitorActive = false;
        let screenshots = {};

        // Socket events
        socket.on('connect', function() {
            console.log('Connected to server');
        });

        socket.on('local_status', function(data) {
            const statusElement = document.getElementById('status');
            if (data.connected) {
                statusElement.textContent = 'Connected';
                statusElement.className = 'connected';
                addToTerminal('Local PC connected!', 'output');
            } else {
                statusElement.textContent = 'Disconnected';
                statusElement.className = 'disconnected';
                addToTerminal('Local PC disconnected!', 'error');
            }
        });

        socket.on('command_result', function(data) {
            addToTerminal(data.output, 'output');
            if (data.cwd) {
                addToTerminal(`[${data.cwd}]`, 'prompt');
            }
        });

        socket.on('screenshot_result', function(data) {
            if (data.success) {
                const timestamp = new Date(data.timestamp * 1000).toLocaleString();
                screenshots[data.timestamp] = {
                    data: data.data,
                    timestamp: timestamp
                };
                refreshScreenshotGallery();
                addToTerminal('Screenshot taken successfully!', 'output');
            } else {
                addToTerminal(`Screenshot error: ${data.error}`, 'error');
            }
        });

        socket.on('live_frame', function(data) {
            if (liveMonitorActive) {
                const img = document.getElementById('liveScreen');
                const placeholder = document.getElementById('monitorPlaceholder');
                img.src = 'data:image/jpeg;base64,' + data.data;
                img.style.display = 'block';
                placeholder.style.display = 'none';
            }
        });

        socket.on('processes_result', function(data) {
            if (data.success) {
                displayProcesses(data.processes, data.opened_from_web);
            } else {
                addToTerminal(`Process list error: ${data.error}`, 'error');
            }
        });

        socket.on('process_killed', function(data) {
            if (data.success) {
                addToTerminal(`Process ${data.pid} terminated successfully`, 'output');
                refreshProcesses();
            } else {
                addToTerminal(`Failed to kill process ${data.pid}: ${data.error}`, 'error');
            }
        });

        // Tab management
        function showTab(tabName) {
            // Hide all tabs
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(content => content.classList.remove('active'));

            // Remove active class from all tabs
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => tab.classList.remove('active'));

            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');

            // Load content if needed
            if (tabName === 'screenshots') {
                refreshScreenshots();
            } else if (tabName === 'processes') {
                refreshProcesses();
            }
        }

        // Terminal functions
        function addToTerminal(text, className) {
            const terminal = document.getElementById('terminalOutput');
            const div = document.createElement('div');
            div.className = className;
            div.textContent = text;
            terminal.appendChild(div);
            terminal.scrollTop = terminal.scrollHeight;
        }

        function sendCommand() {
            const input = document.getElementById('commandInput');
            const command = input.value.trim();
            if (command) {
                addToTerminal(`> ${command}`, 'prompt');
                socket.emit('execute_command', {command: command});
                input.value = '';
            }
        }

        function sendCtrlC() {
            socket.emit('remote_keyboard_action', {action: 'key', key: 'Ctrl+C'});
        }

        // Live monitor functions
        function startLiveMonitor() {
            liveMonitorActive = true;
            socket.emit('start_live_monitoring', {});
            document.getElementById('liveMonitorStatus').textContent = 'Monitor: ON';
            document.getElementById('liveMonitorStatus').className = 'monitor-on';
        }

        function stopLiveMonitor() {
            liveMonitorActive = false;
            socket.emit('stop_live_monitoring', {});
            document.getElementById('liveScreen').style.display = 'none';
            document.getElementById('monitorPlaceholder').style.display = 'block';
            document.getElementById('liveMonitorStatus').textContent = 'Monitor: OFF';
            document.getElementById('liveMonitorStatus').className = 'monitor-off';
        }

        // Screenshot functions
        function takeScreenshot() {
            socket.emit('take_screenshot', {});
        }

        function refreshScreenshots() {
            refreshScreenshotGallery();
        }

        function refreshScreenshotGallery() {
            const gallery = document.getElementById('screenshotGallery');
            gallery.innerHTML = '';

            Object.keys(screenshots).sort().reverse().forEach(timestamp => {
                const item = screenshots[timestamp];
                const div = document.createElement('div');
                div.className = 'screenshot-item';
                div.innerHTML = `
                    <img src="data:image/png;base64,${item.data}" class="screenshot-thumb"
                         onclick="viewFullScreenshot('${timestamp}')" alt="Screenshot">
                    <div style="margin-top: 10px; font-size: 12px;">${item.timestamp}</div>
                    <button onclick="downloadScreenshot('${timestamp}')" class="btn" style="margin-top: 5px; padding: 5px 10px;">Download</button>
                `;
                gallery.appendChild(div);
            });
        }

        function viewFullScreenshot(timestamp) {
            const data = screenshots[timestamp].data;
            const newWindow = window.open();
            newWindow.document.write(`<img src="data:image/png;base64,${data}" style="max-width: 100%; height: auto;">`);
        }

        function downloadScreenshot(timestamp) {
            const data = screenshots[timestamp].data;
            const link = document.createElement('a');
            link.href = 'data:image/png;base64,' + data;
            link.download = `screenshot_${timestamp}.png`;
            link.click();
        }

        // Process management functions
        function refreshProcesses() {
            socket.emit('get_processes', {});
        }

        function displayProcesses(processes, openedFromWeb) {
            const list = document.getElementById('processList');
            list.innerHTML = '';

            processes.forEach(proc => {
                const isFromWeb = openedFromWeb.includes(proc.pid.toString());
                const div = document.createElement('div');
                div.className = 'process-row';
                div.innerHTML = `
                    <div class="process-info">
                        <span><strong>PID:</strong> ${proc.pid}</span>
                        <span><strong>Name:</strong> ${proc.name}</span>
                        <span><strong>Status:</strong> ${proc.status}</span>
                        ${isFromWeb ? '<span style="color: #00ff00;"><strong>[Opened from Web]</strong></span>' : ''}
                    </div>
                    <div class="process-actions">
                        <button onclick="killProcess(${proc.pid})" class="btn btn-danger" style="padding: 5px 10px;">Kill</button>
                    </div>
                `;
                list.appendChild(div);
            });
        }

        function killProcess(pid) {
            if (confirm(`Are you sure you want to kill process ${pid}?`)) {
                socket.emit('kill_process', {pid: pid});
            }
        }

        // Mouse and keyboard handling for live monitor
        document.getElementById('liveScreen').addEventListener('click', function(e) {
            if (liveMonitorActive) {
                const rect = this.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;

                // Scale coordinates to actual screen size
                const scaleX = this.naturalWidth / this.offsetWidth;
                const scaleY = this.naturalHeight / this.offsetHeight;

                socket.emit('remote_mouse_action', {
                    action: 'click',
                    x: Math.round(x * scaleX),
                    y: Math.round(y * scaleY),
                    button: 'left'
                });
            }
        });

        // Keyboard shortcuts
        document.getElementById('commandInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendCommand();
            }
        });

        // Focus on input
        document.getElementById('commandInput').focus();

        // Clean up old screenshots (20 minutes)
        setInterval(function() {
            const now = Date.now() / 1000;
            Object.keys(screenshots).forEach(timestamp => {
                if (now - timestamp > 1200) { // 20 minutes
                    delete screenshots[timestamp];
                }
            });
            refreshScreenshotGallery();
        }, 60000); // Check every minute
    </script>
    {% endif %}
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
        else:
            return render_template_string(HTML_TEMPLATE, authenticated=False, error="Invalid password")

    authenticated = session.get('authenticated', False)
    return render_template_string(HTML_TEMPLATE, authenticated=authenticated)

@app.route('/livemonitoring')
def live_monitoring():
    authenticated = session.get('authenticated', False)
    if not authenticated:
        return redirect(url_for('index'))
    return render_template_string(HTML_TEMPLATE, authenticated=authenticated)

# SocketIO event handlers for web clients
@socketio.on('execute_command')
def handle_web_command(data):
    global local_client_sid, local_connected
    if local_client_sid and local_connected:
        try:
            # Send command to local client
            socketio.emit('execute_command', data, room=local_client_sid)
        except Exception as e:
            emit('command_result', {'output': f'Error sending command: {str(e)}'})
    else:
        emit('command_result', {'output': 'Error: Local PC not connected'})

@socketio.on('take_screenshot')
def handle_take_screenshot(data):
    global local_client_sid, local_connected
    if local_client_sid and local_connected:
        socketio.emit('take_screenshot', data, room=local_client_sid)
    else:
        emit('screenshot_result', {'success': False, 'error': 'Local PC not connected'})

@socketio.on('start_live_monitoring')
def handle_start_live_monitoring(data):
    global local_client_sid, local_connected
    if local_client_sid and local_connected:
        socketio.emit('start_live_monitoring', data, room=local_client_sid)

@socketio.on('stop_live_monitoring')
def handle_stop_live_monitoring(data):
    global local_client_sid, local_connected
    if local_client_sid and local_connected:
        socketio.emit('stop_live_monitoring', data, room=local_client_sid)

@socketio.on('remote_mouse_action')
def handle_remote_mouse_action(data):
    global local_client_sid, local_connected
    if local_client_sid and local_connected:
        socketio.emit('remote_mouse_action', data, room=local_client_sid)

@socketio.on('remote_keyboard_action')
def handle_remote_keyboard_action(data):
    global local_client_sid, local_connected
    if local_client_sid and local_connected:
        socketio.emit('remote_keyboard_action', data, room=local_client_sid)

@socketio.on('get_processes')
def handle_get_processes(data):
    global local_client_sid, local_connected
    if local_client_sid and local_connected:
        socketio.emit('get_processes', data, room=local_client_sid)
    else:
        emit('processes_result', {'success': False, 'error': 'Local PC not connected'})

@socketio.on('kill_process')
def handle_kill_process(data):
    global local_client_sid, local_connected
    if local_client_sid and local_connected:
        socketio.emit('kill_process', data, room=local_client_sid)
    else:
        emit('process_killed', {'success': False, 'error': 'Local PC not connected', 'pid': data['pid']})

# SocketIO event handlers for local client
@socketio.on('local_client_connect')
def handle_local_connect():
    global local_client_sid, local_connected
    local_client_sid = request.sid
    local_connected = True
    print(f"Local client connected: {local_client_sid}")

    # Notify all web clients that local PC is connected
    socketio.emit('local_status', {'connected': True})

@socketio.on('command_result')
def handle_command_result(data):
    # Forward result from local client to all web clients
    socketio.emit('command_result', data)

@socketio.on('screenshot_result')
def handle_screenshot_result(data):
    # Forward screenshot from local client to all web clients
    socketio.emit('screenshot_result', data)

@socketio.on('live_frame')
def handle_live_frame(data):
    # Forward live frame from local client to all web clients
    socketio.emit('live_frame', data)

@socketio.on('processes_result')
def handle_processes_result(data):
    # Forward process list from local client to all web clients
    socketio.emit('processes_result', data)

@socketio.on('process_killed')
def handle_process_killed(data):
    # Forward process kill result from local client to all web clients
    socketio.emit('process_killed', data)

@socketio.on('disconnect')
def handle_disconnect():
    global local_client_sid, local_connected
    if request.sid == local_client_sid:
        print("Local client disconnected")
        local_client_sid = None
        local_connected = False
        # Notify all web clients that local PC is disconnected
        socketio.emit('local_status', {'connected': False})

if __name__ == '__main__':
    print("Starting enhanced Flask app...")
    print("Features: Terminal, Live Monitor, Screenshots, Process Management")

    # Use the PORT environment variable provided by Render
    port = int(os.environ.get('PORT', 5000))

    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)