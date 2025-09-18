from flask import Flask, render_template_string, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
import asyncio
import websockets
import json
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'WEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE@!!!!##########@'
socketio = SocketIO(app, cors_allowed_origins="*")

# Hardcoded password
ADMIN_PASSWORD = "AEae123@"

# Store local client connection
local_client = None
local_connected = False

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Remote Terminal</title>
    <style>
        body {
            background: #1e1e1e;
            color: #ffffff;
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .status {
            background: #2d2d2d;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
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
        .send-btn {
            background: #007acc;
            border: none;
            color: white;
            padding: 10px 20px;
            cursor: pointer;
            font-family: 'Courier New', monospace;
        }
        .send-btn:hover {
            background: #005a9e;
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
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.4/socket.io.js"></script>
</head>
<body>
    {% if not authenticated %}
    <div class="login-form">
        <h2>Remote Terminal Access</h2>
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
        <h1>Remote Terminal</h1>
        <div class="status">
            Local PC Status: <span id="status" class="disconnected">Disconnected</span>
        </div>
        <div class="terminal" id="terminal">
            <div class="output">Welcome to Remote Terminal</div>
            <div class="output">Connecting to local PC...</div>
        </div>
        <div class="input-container">
            <input type="text" id="commandInput" class="command-input" placeholder="Enter command..." autocomplete="off">
            <button onclick="sendCommand()" class="send-btn">Send</button>
        </div>
    </div>

    <script>
        const socket = io();
        const terminal = document.getElementById('terminal');
        const commandInput = document.getElementById('commandInput');
        const statusElement = document.getElementById('status');

        socket.on('connect', function() {
            console.log('Connected to server');
        });

        socket.on('local_status', function(data) {
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

        function addToTerminal(text, className) {
            const div = document.createElement('div');
            div.className = className;
            div.textContent = text;
            terminal.appendChild(div);
            terminal.scrollTop = terminal.scrollHeight;
        }

        function sendCommand() {
            const command = commandInput.value.trim();
            if (command) {
                addToTerminal(`> ${command}`, 'prompt');
                socket.emit('execute_command', {command: command});
                commandInput.value = '';
            }
        }

        commandInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendCommand();
            }
        });

        // Focus on input
        commandInput.focus();
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

@socketio.on('execute_command')
def handle_command(data):
    global local_client
    if local_client and local_connected:
        try:
            command_data = {
                'type': 'command',
                'command': data['command']
            }
            asyncio.run_coroutine_threadsafe(
                local_client.send(json.dumps(command_data)),
                websocket_loop
            )
        except Exception as e:
            emit('command_result', {'output': f'Error sending command: {str(e)}'})
    else:
        emit('command_result', {'output': 'Error: Local PC not connected'})

# WebSocket server for local client
async def handle_local_client(websocket, path):
    global local_client, local_connected

    print(f"Local client connected from {websocket.remote_address}")
    local_client = websocket
    local_connected = True

    # Notify web clients
    socketio.emit('local_status', {'connected': True})

    try:
        async for message in websocket:
            data = json.loads(message)
            if data['type'] == 'result':
                # Send result to web clients
                socketio.emit('command_result', {
                    'output': data['output'],
                    'cwd': data.get('cwd', '')
                })
    except websockets.exceptions.ConnectionClosed:
        print("Local client disconnected")
    except Exception as e:
        print(f"Error with local client: {e}")
    finally:
        local_client = None
        local_connected = False
        socketio.emit('local_status', {'connected': False})

# Start WebSocket server in a separate thread
def start_websocket_server():
    global websocket_loop
    websocket_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(websocket_loop)

    start_server = websockets.serve(handle_local_client, "0.0.0.0", 8765)
    websocket_loop.run_until_complete(start_server)
    websocket_loop.run_forever()

# Start WebSocket server
websocket_thread = threading.Thread(target=start_websocket_server, daemon=True)
websocket_thread.start()

if __name__ == '__main__':
    print("Starting Flask app...")
    print("WebSocket server will listen on port 8765 for local clients")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)