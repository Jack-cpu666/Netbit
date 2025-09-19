from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify, send_file
from flask_socketio import SocketIO, emit, disconnect, join_room, leave_room
import json
import os
import base64
import time
import io
from PIL import Image
import hashlib
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
socketio = SocketIO(app, cors_allowed_origins="*", max_http_buffer_size=10000000)

# Enhanced security with multiple passwords and session management
ADMIN_PASSWORDS = {
    "admin": hashlib.sha256("AEae123@".encode()).hexdigest(),
    "superuser": hashlib.sha256("SuperSecure2024!".encode()).hexdigest()
}

# Session management
active_sessions = {}
local_clients = {}  # Support multiple local clients
web_clients = {}

# Enhanced HTML Template with modern UI
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>UltraTerminal Pro - Advanced Remote Control</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root {
            --bg-primary: #0a0e27;
            --bg-secondary: #1a1f3a;
            --bg-tertiary: #242b48;
            --text-primary: #e4e6eb;
            --text-secondary: #b0b3b8;
            --accent-primary: #00d4ff;
            --accent-secondary: #ff00ff;
            --success: #00ff88;
            --danger: #ff3366;
            --warning: #ffaa00;
            --terminal-bg: #000000;
            --terminal-text: #00ff00;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
            color: var(--text-primary);
            font-family: 'Fira Code', 'Courier New', monospace;
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Animated background */
        .bg-animation {
            position: fixed;
            width: 100%;
            height: 100%;
            top: 0;
            left: 0;
            z-index: -1;
            opacity: 0.1;
            background-image: 
                repeating-linear-gradient(45deg, transparent, transparent 35px, rgba(0, 212, 255, 0.1) 35px, rgba(0, 212, 255, 0.1) 70px);
            animation: bg-scroll 20s linear infinite;
        }

        @keyframes bg-scroll {
            0% { transform: translate(0, 0); }
            100% { transform: translate(70px, 70px); }
        }

        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px;
        }

        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px;
            background: rgba(26, 31, 58, 0.8);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(0, 212, 255, 0.2);
        }

        .logo {
            font-size: 28px;
            font-weight: bold;
            background: linear-gradient(45deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: glow 2s ease-in-out infinite;
        }

        @keyframes glow {
            0%, 100% { filter: drop-shadow(0 0 10px var(--accent-primary)); }
            50% { filter: drop-shadow(0 0 20px var(--accent-secondary)); }
        }

        .status-bar {
            display: flex;
            gap: 20px;
            align-items: center;
        }

        .status-indicator {
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(36, 43, 72, 0.8);
            border: 1px solid rgba(0, 212, 255, 0.3);
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        .status-dot.connected {
            background: var(--success);
        }

        .status-dot.disconnected {
            background: var(--danger);
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(0.8); }
        }

        /* Tab System */
        .tab-container {
            background: rgba(26, 31, 58, 0.6);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }

        .tabs {
            display: flex;
            background: rgba(36, 43, 72, 0.5);
            border-bottom: 2px solid rgba(0, 212, 255, 0.2);
            overflow-x: auto;
        }

        .tab {
            padding: 15px 25px;
            cursor: pointer;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-size: 14px;
            transition: all 0.3s;
            position: relative;
            white-space: nowrap;
        }

        .tab:hover {
            background: rgba(0, 212, 255, 0.1);
            color: var(--text-primary);
        }

        .tab.active {
            color: var(--accent-primary);
            background: rgba(0, 212, 255, 0.2);
        }

        .tab.active::after {
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
            animation: slide-in 0.3s ease;
        }

        @keyframes slide-in {
            from { width: 0; }
            to { width: 100%; }
        }

        .tab-content {
            display: none;
            padding: 20px;
            animation: fade-in 0.3s ease;
        }

        .tab-content.active {
            display: block;
        }

        @keyframes fade-in {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Terminal */
        .terminal-container {
            background: var(--terminal-bg);
            border: 2px solid rgba(0, 212, 255, 0.3);
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.3);
        }

        .terminal-header {
            background: linear-gradient(90deg, rgba(36, 43, 72, 0.9), rgba(26, 31, 58, 0.9));
            padding: 10px 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(0, 212, 255, 0.2);
        }

        .terminal-title {
            font-size: 12px;
            color: var(--text-secondary);
        }

        .terminal-actions {
            display: flex;
            gap: 8px;
        }

        .terminal-btn {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: none;
            cursor: pointer;
            transition: transform 0.2s;
        }

        .terminal-btn:hover {
            transform: scale(1.2);
        }

        .terminal-btn.minimize { background: #ffaa00; }
        .terminal-btn.maximize { background: #00ff88; }
        .terminal-btn.close { background: #ff3366; }

        .terminal {
            height: 500px;
            overflow-y: auto;
            padding: 15px;
            font-family: 'Fira Code', monospace;
            font-size: 14px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .terminal::-webkit-scrollbar {
            width: 10px;
        }

        .terminal::-webkit-scrollbar-track {
            background: rgba(36, 43, 72, 0.5);
        }

        .terminal::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, var(--accent-primary), var(--accent-secondary));
            border-radius: 5px;
        }

        .terminal-output {
            color: var(--terminal-text);
        }

        .terminal-prompt {
            color: var(--accent-primary);
            display: flex;
            align-items: center;
            margin-top: 10px;
        }

        .terminal-cursor {
            display: inline-block;
            width: 8px;
            height: 16px;
            background: var(--terminal-text);
            animation: blink 1s infinite;
            margin-left: 2px;
        }

        @keyframes blink {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0; }
        }

        .terminal-input-container {
            display: flex;
            padding: 15px;
            background: rgba(36, 43, 72, 0.5);
            border-top: 1px solid rgba(0, 212, 255, 0.2);
            gap: 10px;
        }

        .terminal-input {
            flex: 1;
            background: rgba(10, 14, 39, 0.8);
            border: 1px solid rgba(0, 212, 255, 0.3);
            color: var(--terminal-text);
            padding: 12px;
            font-family: 'Fira Code', monospace;
            font-size: 14px;
            border-radius: 5px;
            transition: all 0.3s;
        }

        .terminal-input:focus {
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 10px rgba(0, 212, 255, 0.3);
        }

        /* Buttons */
        .btn {
            padding: 10px 20px;
            background: linear-gradient(45deg, var(--accent-primary), var(--accent-secondary));
            border: none;
            color: white;
            cursor: pointer;
            border-radius: 5px;
            font-weight: 600;
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }

        .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
            transition: left 0.5s;
        }

        .btn:hover::before {
            left: 100%;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 212, 255, 0.3);
        }

        .btn-danger {
            background: linear-gradient(45deg, var(--danger), #ff0066);
        }

        .btn-success {
            background: linear-gradient(45deg, var(--success), #00cc66);
        }

        /* File Manager */
        .file-manager {
            display: grid;
            grid-template-columns: 250px 1fr;
            gap: 20px;
            height: 600px;
        }

        .file-tree {
            background: rgba(36, 43, 72, 0.5);
            border-radius: 10px;
            padding: 15px;
            overflow-y: auto;
            border: 1px solid rgba(0, 212, 255, 0.2);
        }

        .file-content {
            background: rgba(36, 43, 72, 0.5);
            border-radius: 10px;
            padding: 15px;
            overflow-y: auto;
            border: 1px solid rgba(0, 212, 255, 0.2);
        }

        .file-item {
            padding: 8px 12px;
            cursor: pointer;
            border-radius: 5px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .file-item:hover {
            background: rgba(0, 212, 255, 0.1);
        }

        .file-item.selected {
            background: rgba(0, 212, 255, 0.2);
            border-left: 3px solid var(--accent-primary);
        }

        .file-icon {
            font-size: 16px;
        }

        .folder-icon { color: #ffaa00; }
        .file-icon { color: #00d4ff; }

        /* System Monitor */
        .system-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }

        .stat-card {
            background: rgba(36, 43, 72, 0.5);
            border-radius: 10px;
            padding: 20px;
            border: 1px solid rgba(0, 212, 255, 0.2);
            transition: all 0.3s;
        }

        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 212, 255, 0.2);
        }

        .stat-title {
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 10px;
        }

        .stat-value {
            font-size: 32px;
            font-weight: bold;
            background: linear-gradient(45deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .stat-bar {
            height: 6px;
            background: rgba(0, 212, 255, 0.1);
            border-radius: 3px;
            margin-top: 15px;
            overflow: hidden;
        }

        .stat-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
            transition: width 0.5s ease;
            border-radius: 3px;
        }

        /* Live Monitor */
        .monitor-container {
            background: #000;
            border-radius: 10px;
            overflow: hidden;
            position: relative;
            border: 2px solid rgba(0, 212, 255, 0.3);
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.3);
        }

        .monitor-controls {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 10;
            display: flex;
            gap: 10px;
            background: rgba(36, 43, 72, 0.9);
            padding: 10px;
            border-radius: 5px;
        }

        .screen {
            width: 100%;
            height: auto;
            display: block;
        }

        /* Process Manager */
        .process-table {
            width: 100%;
            background: rgba(36, 43, 72, 0.5);
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid rgba(0, 212, 255, 0.2);
        }

        .process-header {
            display: grid;
            grid-template-columns: 100px 2fr 1fr 1fr 150px;
            padding: 15px;
            background: rgba(26, 31, 58, 0.8);
            font-weight: 600;
            color: var(--text-secondary);
            border-bottom: 2px solid rgba(0, 212, 255, 0.2);
        }

        .process-row {
            display: grid;
            grid-template-columns: 100px 2fr 1fr 1fr 150px;
            padding: 12px 15px;
            transition: all 0.2s;
            border-bottom: 1px solid rgba(0, 212, 255, 0.1);
        }

        .process-row:hover {
            background: rgba(0, 212, 255, 0.1);
        }

        /* Animations for notifications */
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            animation: slide-in-right 0.3s ease;
            z-index: 1000;
            max-width: 400px;
        }

        @keyframes slide-in-right {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .notification.success {
            background: linear-gradient(45deg, var(--success), #00cc66);
            color: white;
        }

        .notification.error {
            background: linear-gradient(45deg, var(--danger), #ff0066);
            color: white;
        }

        .notification.info {
            background: linear-gradient(45deg, var(--accent-primary), var(--accent-secondary));
            color: white;
        }

        /* Login Page */
        .login-container {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .login-form {
            background: rgba(26, 31, 58, 0.9);
            backdrop-filter: blur(10px);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(0, 212, 255, 0.2);
            width: 400px;
        }

        .login-logo {
            text-align: center;
            font-size: 48px;
            margin-bottom: 20px;
            background: linear-gradient(45deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .login-input {
            width: 100%;
            padding: 15px;
            margin: 10px 0;
            background: rgba(10, 14, 39, 0.8);
            border: 1px solid rgba(0, 212, 255, 0.3);
            color: var(--text-primary);
            border-radius: 10px;
            font-size: 16px;
        }

        .login-input:focus {
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 10px rgba(0, 212, 255, 0.3);
        }

        /* Responsive Design */
        @media (max-width: 768px) {
            .file-manager {
                grid-template-columns: 1fr;
            }
            
            .tabs {
                overflow-x: auto;
            }
            
            .system-stats {
                grid-template-columns: 1fr;
            }
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.4/socket.io.js"></script>
</head>
<body>
    <div class="bg-animation"></div>
    
    {% if not authenticated %}
    <div class="login-container">
        <div class="login-form">
            <div class="login-logo">🚀</div>
            <h2 style="text-align: center; margin-bottom: 30px;">UltraTerminal Pro</h2>
            <form method="POST">
                <input type="text" name="username" placeholder="Username" class="login-input" required>
                <input type="password" name="password" placeholder="Password" class="login-input" required>
                <button type="submit" class="btn" style="width: 100%; margin-top: 20px;">
                    Access System
                </button>
            </form>
            {% if error %}
            <p style="color: var(--danger); margin-top: 20px; text-align: center;">{{ error }}</p>
            {% endif %}
        </div>
    </div>
    {% else %}
    <div class="container">
        <div class="header">
            <div class="logo">🚀 UltraTerminal Pro</div>
            <div class="status-bar">
                <div class="status-indicator">
                    <span class="status-dot" id="mainStatus"></span>
                    <span id="statusText">Connecting...</span>
                </div>
                <div class="status-indicator">
                    <span>CPU:</span>
                    <span id="cpuUsage">0%</span>
                </div>
                <div class="status-indicator">
                    <span>RAM:</span>
                    <span id="memUsage">0%</span>
                </div>
                <div class="status-indicator">
                    <span>User:</span>
                    <span>{{ username }}</span>
                </div>
            </div>
        </div>

        <div class="tab-container">
            <div class="tabs">
                <button class="tab active" onclick="switchTab('terminal')">🖥️ Terminal</button>
                <button class="tab" onclick="switchTab('filemanager')">📁 File Manager</button>
                <button class="tab" onclick="switchTab('monitor')">👁️ Live Monitor</button>
                <button class="tab" onclick="switchTab('processes')">⚙️ Processes</button>
                <button class="tab" onclick="switchTab('system')">📊 System Info</button>
                <button class="tab" onclick="switchTab('tools')">🛠️ Tools</button>
            </div>

            <!-- Terminal Tab -->
            <div id="terminal" class="tab-content active">
                <div class="terminal-container">
                    <div class="terminal-header">
                        <div class="terminal-title">
                            <span id="terminalPath">C:\\</span> - Admin Terminal
                        </div>
                        <div class="terminal-actions">
                            <button class="terminal-btn minimize" onclick="minimizeTerminal()"></button>
                            <button class="terminal-btn maximize" onclick="maximizeTerminal()"></button>
                            <button class="terminal-btn close" onclick="clearTerminal()"></button>
                        </div>
                    </div>
                    <div class="terminal" id="terminalOutput">
                        <div class="terminal-output">UltraTerminal Pro v2.0 - Enhanced Remote Terminal</div>
                        <div class="terminal-output">Type 'help' for available commands</div>
                        <div class="terminal-output">─────────────────────────────────────────────</div>
                    </div>
                    <div class="terminal-input-container">
                        <input type="text" 
                               id="terminalInput" 
                               class="terminal-input" 
                               placeholder="Enter command..." 
                               autocomplete="off"
                               autofocus>
                        <button onclick="sendCommand()" class="btn">Execute</button>
                        <button onclick="sendSpecialKey('ctrl+c')" class="btn btn-danger">Ctrl+C</button>
                        <button onclick="sendSpecialKey('ctrl+z')" class="btn">Ctrl+Z</button>
                    </div>
                </div>
            </div>

            <!-- File Manager Tab -->
            <div id="filemanager" class="tab-content">
                <div class="file-manager">
                    <div class="file-tree">
                        <h3 style="margin-bottom: 15px; color: var(--accent-primary);">Directory Tree</h3>
                        <div id="fileTree">
                            <!-- File tree will be populated here -->
                        </div>
                    </div>
                    <div class="file-content">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                            <input type="text" 
                                   id="currentPath" 
                                   class="terminal-input" 
                                   style="flex: 1; margin-right: 10px;"
                                   placeholder="Current path...">
                            <button onclick="refreshDirectory()" class="btn">Refresh</button>
                            <input type="file" 
                                   id="fileUpload" 
                                   style="display: none;" 
                                   onchange="uploadFile(this)">
                            <button onclick="document.getElementById('fileUpload').click()" class="btn">Upload</button>
                        </div>
                        <div id="fileList">
                            <!-- File list will be populated here -->
                        </div>
                    </div>
                </div>
            </div>

            <!-- Live Monitor Tab -->
            <div id="monitor" class="tab-content">
                <div style="margin-bottom: 20px;">
                    <button onclick="startLiveMonitor()" class="btn btn-success">▶️ Start Monitoring</button>
                    <button onclick="stopLiveMonitor()" class="btn btn-danger">⏹️ Stop Monitoring</button>
                    <button onclick="takeScreenshot()" class="btn">📸 Screenshot</button>
                    <label style="margin-left: 20px;">
                        Quality: 
                        <input type="range" id="quality" min="30" max="100" value="60" 
                               style="width: 150px; vertical-align: middle;">
                        <span id="qualityValue">60%</span>
                    </label>
                    <label style="margin-left: 20px;">
                        FPS: 
                        <input type="range" id="fps" min="5" max="30" value="10" 
                               style="width: 150px; vertical-align: middle;">
                        <span id="fpsValue">10</span>
                    </label>
                </div>
                <div class="monitor-container">
                    <div class="monitor-controls">
                        <button id="mouseToggle" class="btn" onclick="toggleMouseControl()">🖱️ Mouse: ON</button>
                    </div>
                    <img id="liveScreen" class="screen" style="display: none;">
                    <div id="monitorPlaceholder" style="padding: 100px; text-align: center; color: var(--text-secondary);">
                        Live monitor will appear here
                    </div>
                </div>
            </div>

            <!-- Processes Tab -->
            <div id="processes" class="tab-content">
                <div style="margin-bottom: 20px;">
                    <button onclick="refreshProcesses()" class="btn">🔄 Refresh</button>
                    <input type="text" 
                           id="processFilter" 
                           placeholder="Filter processes..." 
                           class="terminal-input" 
                           style="width: 300px; margin-left: 10px;"
                           oninput="filterProcesses()">
                </div>
                <div class="process-table">
                    <div class="process-header">
                        <div>PID</div>
                        <div>Name</div>
                        <div>Status</div>
                        <div>CPU %</div>
                        <div>Actions</div>
                    </div>
                    <div id="processList">
                        <!-- Processes will be populated here -->
                    </div>
                </div>
            </div>

            <!-- System Info Tab -->
            <div id="system" class="tab-content">
                <div style="margin-bottom: 20px;">
                    <button onclick="getSystemInfo()" class="btn">🔄 Refresh Info</button>
                    <button onclick="startSystemMonitoring()" class="btn btn-success">▶️ Real-time Monitor</button>
                    <button onclick="stopSystemMonitoring()" class="btn btn-danger">⏹️ Stop Monitor</button>
                </div>
                <div class="system-stats">
                    <div class="stat-card">
                        <div class="stat-title">CPU Usage</div>
                        <div class="stat-value" id="cpuStat">0%</div>
                        <div class="stat-bar">
                            <div class="stat-bar-fill" id="cpuBar" style="width: 0%"></div>
                        </div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Memory Usage</div>
                        <div class="stat-value" id="memStat">0%</div>
                        <div class="stat-bar">
                            <div class="stat-bar-fill" id="memBar" style="width: 0%"></div>
                        </div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Disk Usage</div>
                        <div class="stat-value" id="diskStat">0%</div>
                        <div class="stat-bar">
                            <div class="stat-bar-fill" id="diskBar" style="width: 0%"></div>
                        </div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Network</div>
                        <div class="stat-value" id="netStat" style="font-size: 16px;">↑ 0 MB ↓ 0 MB</div>
                    </div>
                </div>
                <div id="systemDetails" style="margin-top: 20px;">
                    <!-- Detailed system info will appear here -->
                </div>
            </div>

            <!-- Tools Tab -->
            <div id="tools" class="tab-content">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
                    <button onclick="getClipboard()" class="btn" style="height: 80px;">
                        📋 Get Clipboard
                    </button>
                    <button onclick="setClipboard()" class="btn" style="height: 80px;">
                        📝 Set Clipboard
                    </button>
                    <button onclick="restartTerminal()" class="btn btn-warning" style="height: 80px;">
                        🔄 Restart Terminal
                    </button>
                    <button onclick="shutdownSystem()" class="btn btn-danger" style="height: 80px;">
                        🔴 Shutdown System
                    </button>
                </div>
                <div id="toolsOutput" style="margin-top: 20px;">
                    <!-- Tools output will appear here -->
                </div>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        let currentPath = 'C:\\\\';
        let liveMonitorActive = false;
        let mouseControlEnabled = true;
        let terminalBuffer = [];
        let systemMonitoringActive = false;

        // Socket connection handlers
        socket.on('connect', function() {
            console.log('Connected to server');
            showNotification('Connected to server', 'success');
        });

        socket.on('local_client_connect', function(data) {
            document.getElementById('mainStatus').className = 'status-dot connected';
            document.getElementById('statusText').textContent = `Connected to ${data.hostname}`;
            currentPath = data.cwd;
            document.getElementById('terminalPath').textContent = currentPath;
            document.getElementById('currentPath').value = currentPath;
            showNotification(`Connected to ${data.hostname} as ${data.username}`, 'success');
        });

        socket.on('local_status', function(data) {
            const statusDot = document.getElementById('mainStatus');
            const statusText = document.getElementById('statusText');
            
            if (data.connected) {
                statusDot.className = 'status-dot connected';
                statusText.textContent = 'PC Connected';
            } else {
                statusDot.className = 'status-dot disconnected';
                statusText.textContent = 'PC Disconnected';
            }
        });

        // Enhanced terminal output handling
        socket.on('terminal_output', function(data) {
            const terminal = document.getElementById('terminalOutput');
            const output = document.createElement('div');
            output.className = 'terminal-output';
            
            if (data.type === 'command') {
                output.style.color = 'var(--accent-primary)';
            } else if (data.type === 'error') {
                output.style.color = 'var(--danger)';
            }
            
            output.textContent = data.data;
            terminal.appendChild(output);
            terminal.scrollTop = terminal.scrollHeight;
            
            // Keep buffer manageable
            terminalBuffer.push(data.data);
            if (terminalBuffer.length > 1000) {
                terminalBuffer = terminalBuffer.slice(-500);
            }
        });

        socket.on('directory_changed', function(data) {
            if (data.success) {
                currentPath = data.new_path;
                document.getElementById('terminalPath').textContent = currentPath;
                document.getElementById('currentPath').value = currentPath;
                refreshDirectory();
            } else {
                showNotification(`Failed to change directory: ${data.error}`, 'error');
            }
        });

        socket.on('directory_listing', function(data) {
            if (data.success) {
                displayFiles(data.items);
            } else {
                showNotification(`Failed to list directory: ${data.error}`, 'error');
            }
        });

        socket.on('system_info', function(data) {
            if (data.success) {
                updateSystemInfo(data.info);
            }
        });

        socket.on('system_stats_update', function(data) {
            updateSystemStats(data);
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

        // Terminal functions
        function sendCommand() {
            const input = document.getElementById('terminalInput');
            const command = input.value.trim();
            
            if (command) {
                socket.emit('terminal_command', { command: command });
                
                // Add to terminal display
                const terminal = document.getElementById('terminalOutput');
                const cmdDiv = document.createElement('div');
                cmdDiv.className = 'terminal-output';
                cmdDiv.style.color = 'var(--accent-primary)';
                cmdDiv.textContent = `> ${command}`;
                terminal.appendChild(cmdDiv);
                terminal.scrollTop = terminal.scrollHeight;
                
                input.value = '';
            }
        }

        // Real-time typing in terminal
        document.getElementById('terminalInput').addEventListener('input', function(e) {
            const text = e.target.value;
            socket.emit('terminal_input', { text: text });
        });

        document.getElementById('terminalInput').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendCommand();
            } else if (e.key === 'Tab') {
                e.preventDefault();
                sendSpecialKey('tab');
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                sendSpecialKey('up');
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                sendSpecialKey('down');
            }
        });

        function sendSpecialKey(key) {
            socket.emit('terminal_special_key', { key: key });
        }

        function clearTerminal() {
            document.getElementById('terminalOutput').innerHTML = '';
            terminalBuffer = [];
        }

        function minimizeTerminal() {
            const terminal = document.querySelector('.terminal');
            terminal.style.height = '200px';
        }

        function maximizeTerminal() {
            const terminal = document.querySelector('.terminal');
            terminal.style.height = '500px';
        }

        function restartTerminal() {
            socket.emit('restart_terminal', {});
            showNotification('Terminal restarted', 'info');
        }

        // Tab switching
        function switchTab(tabName) {
            // Hide all tab contents
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(content => content.classList.remove('active'));
            
            // Remove active from all tabs
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => tab.classList.remove('active'));
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
            
            // Load content if needed
            if (tabName === 'filemanager') {
                refreshDirectory();
            } else if (tabName === 'processes') {
                refreshProcesses();
            } else if (tabName === 'system') {
                getSystemInfo();
            }
        }

        // File Manager functions
        function refreshDirectory() {
            const path = document.getElementById('currentPath').value || currentPath;
            socket.emit('list_directory', { path: path });
        }

        function displayFiles(items) {
            const fileList = document.getElementById('fileList');
            fileList.innerHTML = '';
            
            // Add parent directory navigation if available
            const parentBtn = document.createElement('div');
            parentBtn.className = 'file-item';
            parentBtn.innerHTML = `
                <span class="file-icon folder-icon">⬆️</span>
                <span style="flex: 1;">.. (Parent Directory)</span>
            `;
            parentBtn.onclick = () => navigateToParent();
            fileList.appendChild(parentBtn);
            
            // Sort: directories first, then files
            items.sort((a, b) => {
                if (a.type === 'dir' && b.type !== 'dir') return -1;
                if (a.type !== 'dir' && b.type === 'dir') return 1;
                return a.name.localeCompare(b.name);
            });
            
            items.forEach(item => {
                const div = document.createElement('div');
                div.className = 'file-item';
                
                const isFolder = item.type === 'dir';
                const icon = isFolder ? '📁' : getFileIcon(item.name);
                
                div.innerHTML = `
                    <span class="file-icon ${isFolder ? 'folder-icon' : 'file-icon'}">
                        ${icon}
                    </span>
                    <span style="flex: 1;">${item.name}</span>
                    <span style="color: var(--text-secondary); margin-right: 10px;">
                        ${isFolder ? 'Folder' : formatFileSize(item.size)}
                    </span>
                    <button onclick="event.stopPropagation(); downloadItem('${item.full_path || (currentPath + '\\\\' + item.name)}', ${isFolder})" 
                            class="btn btn-success" style="padding: 5px 10px; margin-right: 5px;">
                        ⬇️
                    </button>
                    ${!isFolder ? `
                    <button onclick="event.stopPropagation(); openFile('${item.full_path || (currentPath + '\\\\' + item.name)}')" 
                            class="btn" style="padding: 5px 10px; margin-right: 5px;">
                        📂
                    </button>
                    ` : ''}
                    <button onclick="event.stopPropagation(); deleteItem('${item.full_path || (currentPath + '\\\\' + item.name)}')" 
                            class="btn btn-danger" style="padding: 5px 10px;">
                        🗑️
                    </button>
                `;
                
                if (isFolder) {
                    div.onclick = () => navigateToDirectory(item.full_path || (currentPath + '\\\\' + item.name));
                }
                
                fileList.appendChild(div);
            });
        }

        function getFileIcon(filename) {
            const ext = filename.split('.').pop().toLowerCase();
            const icons = {
                'txt': '📄', 'doc': '📝', 'docx': '📝',
                'pdf': '📕', 'xls': '📊', 'xlsx': '📊',
                'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️',
                'mp3': '🎵', 'mp4': '🎥', 'avi': '🎥',
                'zip': '🗜️', 'rar': '🗜️', '7z': '🗜️',
                'exe': '⚙️', 'py': '🐍', 'js': '📜',
                'html': '🌐', 'css': '🎨', 'json': '📋'
            };
            return icons[ext] || '📄';
        }

        function navigateToDirectory(path) {
            socket.emit('change_directory', { path: path });
        }

        function navigateToParent() {
            socket.emit('navigate_up', {});
        }

        function downloadItem(path, isFolder) {
            socket.emit('download_file', { path: path });
            showNotification(`Downloading ${isFolder ? 'folder' : 'file'}...`, 'info');
        }

        function openFile(path) {
            socket.emit('open_file', { path: path });
            showNotification('Opening file...', 'info');
        }

        function deleteItem(path) {
            const itemName = path.split('\\\\').pop();
            if (confirm(`Are you sure you want to delete "${itemName}"?`)) {
                socket.emit('delete_file', { path: path });
            }
        }

        function uploadFile(input) {
            const file = input.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const arrayBuffer = e.target.result;
                    const bytes = new Uint8Array(arrayBuffer);
                    let binary = '';
                    for (let i = 0; i < bytes.byteLength; i++) {
                        binary += String.fromCharCode(bytes[i]);
                    }
                    const content = btoa(binary);
                    
                    socket.emit('upload_file', {
                        filename: file.name,
                        content: content,
                        path: currentPath
                    });
                    showNotification(`Uploading ${file.name}...`, 'info');
                };
                reader.readAsArrayBuffer(file);
                input.value = '';  // Reset input
            }
        }

        // Handle file download responses
        socket.on('file_download', function(data) {
            if (data.success) {
                // Create download link
                const link = document.createElement('a');
                const bytes = atob(data.content);
                const numbers = new Uint8Array(bytes.length);
                for (let i = 0; i < bytes.length; i++) {
                    numbers[i] = bytes.charCodeAt(i);
                }
                const blob = new Blob([numbers]);
                const url = URL.createObjectURL(blob);
                
                link.href = url;
                link.download = data.filename;
                link.click();
                
                URL.revokeObjectURL(url);
                showNotification(`Downloaded ${data.filename}`, 'success');
            } else {
                showNotification(`Download failed: ${data.error}`, 'error');
            }
        });

        socket.on('file_uploaded', function(data) {
            if (data.success) {
                showNotification(`Uploaded ${data.filename}`, 'success');
                refreshDirectory();
            } else {
                showNotification(`Upload failed: ${data.error}`, 'error');
            }
        });

        socket.on('file_deleted', function(data) {
            if (data.success) {
                showNotification('Item deleted', 'success');
                refreshDirectory();
            } else {
                showNotification(`Delete failed: ${data.error}`, 'error');
            }
        });

        socket.on('file_opened', function(data) {
            if (data.success) {
                showNotification('File opened', 'success');
            } else {
                showNotification(`Failed to open file: ${data.error}`, 'error');
            }
        });

        // Monitor functions
        function startLiveMonitor() {
            liveMonitorActive = true;
            const quality = document.getElementById('quality').value;
            const fps = document.getElementById('fps').value;
            socket.emit('start_live_monitoring', { quality: quality, fps: fps });
            showNotification('Live monitoring started', 'success');
        }

        function stopLiveMonitor() {
            liveMonitorActive = false;
            socket.emit('stop_live_monitoring', {});
            document.getElementById('liveScreen').style.display = 'none';
            document.getElementById('monitorPlaceholder').style.display = 'block';
            showNotification('Live monitoring stopped', 'info');
        }

        function takeScreenshot() {
            socket.emit('take_screenshot', { quality: 85 });
        }

        function toggleMouseControl() {
            mouseControlEnabled = !mouseControlEnabled;
            const btn = document.getElementById('mouseToggle');
            btn.textContent = mouseControlEnabled ? '🖱️ Mouse: ON' : '🖱️ Mouse: OFF';
            btn.className = mouseControlEnabled ? 'btn btn-success' : 'btn btn-danger';
        }

        // Process Manager
        function refreshProcesses() {
            socket.emit('get_processes', {});
        }

        function filterProcesses() {
            const filter = document.getElementById('processFilter').value.toLowerCase();
            const rows = document.querySelectorAll('.process-row');
            rows.forEach(row => {
                const name = row.querySelector('.process-name').textContent.toLowerCase();
                row.style.display = name.includes(filter) ? '' : 'none';
            });
        }

        // System functions
        function getSystemInfo() {
            socket.emit('get_system_info', {});
        }

        function startSystemMonitoring() {
            systemMonitoringActive = true;
            socket.emit('start_system_monitoring', {});
            showNotification('System monitoring started', 'success');
        }

        function stopSystemMonitoring() {
            systemMonitoringActive = false;
            socket.emit('stop_system_monitoring', {});
            showNotification('System monitoring stopped', 'info');
        }

        function updateSystemInfo(info) {
            document.getElementById('cpuStat').textContent = info.cpu.percent.toFixed(1) + '%';
            document.getElementById('cpuBar').style.width = info.cpu.percent + '%';
            
            document.getElementById('memStat').textContent = info.memory.percent.toFixed(1) + '%';
            document.getElementById('memBar').style.width = info.memory.percent + '%';
            
            document.getElementById('diskStat').textContent = info.disk.percent.toFixed(1) + '%';
            document.getElementById('diskBar').style.width = info.disk.percent + '%';
            
            const sent = (info.network.bytes_sent / 1024 / 1024).toFixed(2);
            const recv = (info.network.bytes_recv / 1024 / 1024).toFixed(2);
            document.getElementById('netStat').innerHTML = `↑ ${sent} MB<br>↓ ${recv} MB`;
            
            // Update header stats
            document.getElementById('cpuUsage').textContent = info.cpu.percent.toFixed(1) + '%';
            document.getElementById('memUsage').textContent = info.memory.percent.toFixed(1) + '%';
        }

        function updateSystemStats(stats) {
            if (systemMonitoringActive) {
                document.getElementById('cpuStat').textContent = stats.cpu.toFixed(1) + '%';
                document.getElementById('cpuBar').style.width = stats.cpu + '%';
                document.getElementById('cpuUsage').textContent = stats.cpu.toFixed(1) + '%';
                
                document.getElementById('memStat').textContent = stats.memory.toFixed(1) + '%';
                document.getElementById('memBar').style.width = stats.memory + '%';
                document.getElementById('memUsage').textContent = stats.memory.toFixed(1) + '%';
                
                document.getElementById('diskStat').textContent = stats.disk.toFixed(1) + '%';
                document.getElementById('diskBar').style.width = stats.disk + '%';
            }
        }

        // Tools functions
        function getClipboard() {
            socket.emit('get_clipboard', {});
        }

        function setClipboard() {
            const content = prompt('Enter text to set in clipboard:');
            if (content !== null) {
                socket.emit('set_clipboard', { content: content });
            }
        }

        function shutdownSystem() {
            if (confirm('Are you sure you want to shutdown the remote system?')) {
                socket.emit('shutdown_system', {});
            }
        }

        // Utility functions
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        function showNotification(message, type = 'info') {
            const notification = document.createElement('div');
            notification.className = `notification ${type}`;
            notification.textContent = message;
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.style.opacity = '0';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }

        // Quality and FPS sliders
        document.getElementById('quality').addEventListener('input', function(e) {
            document.getElementById('qualityValue').textContent = e.target.value + '%';
        });

        document.getElementById('fps').addEventListener('input', function(e) {
            document.getElementById('fpsValue').textContent = e.target.value;
        });

        // Initialize
        document.getElementById('terminalInput').focus();
    </script>
    {% endif %}
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if username in ADMIN_PASSWORDS and ADMIN_PASSWORDS[username] == password_hash:
            session['authenticated'] = True
            session['username'] = username
            session['session_id'] = secrets.token_hex(16)
            active_sessions[session['session_id']] = {
                'username': username,
                'login_time': datetime.now(),
                'last_activity': datetime.now()
            }
            return redirect(url_for('index'))
        else:
            return render_template_string(HTML_TEMPLATE, authenticated=False, error="Invalid credentials")

    authenticated = session.get('authenticated', False)
    username = session.get('username', 'Guest')
    return render_template_string(HTML_TEMPLATE, authenticated=authenticated, username=username)

# Enhanced SocketIO handlers for web clients
@socketio.on('connect')
def handle_web_connect():
    if session.get('authenticated'):
        session_id = session.get('session_id')
        web_clients[request.sid] = {
            'username': session.get('username'),
            'session_id': session_id,
            'connected_at': datetime.now()
        }
        join_room('web_clients')
        
        # Notify about any connected local clients
        for local_sid, local_info in local_clients.items():
            emit('local_client_connect', local_info)

# Local client handlers
@socketio.on('local_client_connect')
def handle_local_connect(data):
    local_clients[request.sid] = data
    join_room('local_clients')
    
    # Notify all web clients
    socketio.emit('local_client_connect', data, room='web_clients')
    socketio.emit('local_status', {'connected': True}, room='web_clients')

# Terminal handlers
@socketio.on('terminal_command')
def handle_terminal_command(data):
    # Forward to all local clients
    socketio.emit('terminal_command', data, room='local_clients')

@socketio.on('terminal_input')
def handle_terminal_input(data):
    # Forward real-time input to local clients
    socketio.emit('terminal_input', data, room='local_clients')

@socketio.on('terminal_special_key')
def handle_terminal_special_key(data):
    socketio.emit('terminal_special_key', data, room='local_clients')

@socketio.on('terminal_output')
def handle_terminal_output(data):
    # Forward terminal output from local to web clients
    socketio.emit('terminal_output', data, room='web_clients')

# File management handlers
@socketio.on('list_directory')
def handle_list_directory(data):
    socketio.emit('list_directory', data, room='local_clients')

@socketio.on('directory_listing')
def handle_directory_listing(data):
    socketio.emit('directory_listing', data, room='web_clients')

@socketio.on('change_directory')
def handle_change_directory(data):
    socketio.emit('change_directory', data, room='local_clients')

@socketio.on('directory_changed')
def handle_directory_changed(data):
    socketio.emit('directory_changed', data, room='web_clients')

@socketio.on('navigate_up')
def handle_navigate_up(data):
    socketio.emit('navigate_up', data, room='local_clients')

@socketio.on('upload_file')
def handle_upload_file(data):
    socketio.emit('upload_file', data, room='local_clients')

@socketio.on('file_uploaded')
def handle_file_uploaded(data):
    socketio.emit('file_uploaded', data, room='web_clients')

@socketio.on('download_file')
def handle_download_file(data):
    socketio.emit('download_file', data, room='local_clients')

@socketio.on('file_download')
def handle_file_download(data):
    socketio.emit('file_download', data, room='web_clients')

@socketio.on('delete_file')
def handle_delete_file(data):
    socketio.emit('delete_file', data, room='local_clients')

@socketio.on('file_deleted')
def handle_file_deleted(data):
    socketio.emit('file_deleted', data, room='web_clients')

@socketio.on('open_file')
def handle_open_file(data):
    socketio.emit('open_file', data, room='local_clients')

@socketio.on('file_opened')
def handle_file_opened(data):
    socketio.emit('file_opened', data, room='web_clients')

# System monitoring handlers
@socketio.on('get_system_info')
def handle_get_system_info(data):
    socketio.emit('get_system_info', data, room='local_clients')

@socketio.on('system_info')
def handle_system_info(data):
    socketio.emit('system_info', data, room='web_clients')

@socketio.on('start_system_monitoring')
def handle_start_system_monitoring(data):
    socketio.emit('start_system_monitoring', data, room='local_clients')

@socketio.on('stop_system_monitoring')
def handle_stop_system_monitoring(data):
    socketio.emit('stop_system_monitoring', data, room='local_clients')

@socketio.on('system_stats_update')
def handle_system_stats_update(data):
    socketio.emit('system_stats_update', data, room='web_clients')

# Live monitoring handlers
@socketio.on('start_live_monitoring')
def handle_start_live_monitoring(data):
    socketio.emit('start_live_monitoring', data, room='local_clients')

@socketio.on('stop_live_monitoring')
def handle_stop_live_monitoring(data):
    socketio.emit('stop_live_monitoring', data, room='local_clients')

@socketio.on('live_frame')
def handle_live_frame(data):
    socketio.emit('live_frame', data, room='web_clients')

# Screenshot handlers
@socketio.on('take_screenshot')
def handle_take_screenshot(data):
    socketio.emit('take_screenshot', data, room='local_clients')

@socketio.on('screenshot_result')
def handle_screenshot_result(data):
    socketio.emit('screenshot_result', data, room='web_clients')

# Clipboard handlers
@socketio.on('get_clipboard')
def handle_get_clipboard(data):
    socketio.emit('get_clipboard', data, room='local_clients')

@socketio.on('clipboard_content')
def handle_clipboard_content(data):
    socketio.emit('clipboard_content', data, room='web_clients')

@socketio.on('set_clipboard')
def handle_set_clipboard(data):
    socketio.emit('set_clipboard', data, room='local_clients')

@socketio.on('clipboard_set')
def handle_clipboard_set(data):
    socketio.emit('clipboard_set', data, room='web_clients')

# Process management handlers
@socketio.on('get_processes')
def handle_get_processes(data):
    socketio.emit('get_processes', data, room='local_clients')

@socketio.on('processes_result')
def handle_processes_result(data):
    socketio.emit('processes_result', data, room='web_clients')

# Disconnect handler
@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in local_clients:
        del local_clients[request.sid]
        leave_room('local_clients')
        socketio.emit('local_status', {'connected': False}, room='web_clients')
    
    if request.sid in web_clients:
        del web_clients[request.sid]
        leave_room('web_clients')

if __name__ == '__main__':
    print("🚀 Starting UltraTerminal Pro Server v2.0")
    print("=" * 50)
    print("Enhanced Features:")
    print("  ✅ Real-time bidirectional terminal")
    print("  ✅ Advanced file management")
    print("  ✅ System monitoring dashboard")
    print("  ✅ Professional UI with animations")
    print("  ✅ Multi-user support")
    print("=" * 50)
    
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
