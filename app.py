import socketio
import subprocess
import json
import sys
import os
import ctypes
import platform
import time
import threading
import base64
import io
import signal
import queue
import select
import msvcrt
from PIL import Image, ImageGrab
import psutil
from pynput import mouse, keyboard
from pynput.mouse import Button, Listener as MouseListener
from pynput.keyboard import Key, Listener as KeyboardListener
import cv2
import numpy as np
import win32gui
import win32con
import win32api
import win32console
import win32process
import pywintypes
from datetime import datetime
import hashlib
import zipfile
import shutil

def is_admin():
    """Check if running with admin privileges on Windows"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Restart the script with admin privileges"""
    if platform.system() == "Windows":
        if is_admin():
            return True
        else:
            print("Requesting administrator privileges...")
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            return False
    return True

class EnhancedLocalClient:
    def __init__(self, server_url):
        self.server_url = server_url
        self.sio = socketio.Client()
        self.start_time = None
        self.max_reconnect_duration = 24 * 60 * 60
        self.live_monitoring = False
        self.opened_processes = {}
        self.running = True
        self.terminal_process = None
        self.current_directory = os.getcwd()
        self.command_queue = queue.Queue()
        self.output_buffer = []
        self.terminal_thread = None
        self.file_transfer_sessions = {}
        self.system_stats_thread = None
        self.send_system_stats = False
        self.clipboard_content = ""
        self.terminal_buffer = []
        self.max_buffer_size = 10000
        self.setup_handlers()
        self.start_enhanced_terminal()

    def setup_handlers(self):
        @self.sio.event
        def connect():
            print("✅ Connected to render server!")
            self.start_time = None
            # Send initial system info
            self.sio.emit('local_client_connect', {
                'hostname': os.environ.get('COMPUTERNAME', 'Unknown'),
                'username': os.environ.get('USERNAME', 'Unknown'),
                'os': platform.system(),
                'os_version': platform.version(),
                'python_version': sys.version,
                'admin': is_admin(),
                'cwd': self.current_directory
            })

        @self.sio.event
        def disconnect():
            print("❌ Disconnected from server")
            self.live_monitoring = False
            self.send_system_stats = False

        @self.sio.event
        def terminal_input(data):
            """Handle real-time terminal input from website"""
            text = data.get('text', '')
            if self.terminal_process and self.terminal_process.poll() is None:
                try:
                    self.terminal_process.stdin.write(text)
                    self.terminal_process.stdin.flush()
                except Exception as e:
                    print(f"Error writing to terminal: {e}")

        @self.sio.event
        def terminal_command(data):
            """Execute a complete command"""
            command = data.get('command', '')
            if command:
                self.command_queue.put(command)

        @self.sio.event
        def terminal_special_key(data):
            """Handle special keys like Ctrl+C, Ctrl+Z, etc."""
            key = data.get('key', '')
            if self.terminal_process and self.terminal_process.poll() is None:
                try:
                    if key == 'ctrl+c':
                        # Send SIGINT to process group
                        if platform.system() == "Windows":
                            self.terminal_process.send_signal(signal.CTRL_C_EVENT)
                        else:
                            self.terminal_process.send_signal(signal.SIGINT)
                    elif key == 'ctrl+z':
                        if platform.system() == "Windows":
                            self.terminal_process.send_signal(signal.CTRL_BREAK_EVENT)
                        else:
                            self.terminal_process.send_signal(signal.SIGTSTP)
                    elif key == 'tab':
                        self.terminal_process.stdin.write('\t')
                        self.terminal_process.stdin.flush()
                    elif key == 'up':
                        # Send up arrow for command history
                        if platform.system() == "Windows":
                            self.terminal_process.stdin.write('\x1b[A')
                        self.terminal_process.stdin.flush()
                    elif key == 'down':
                        if platform.system() == "Windows":
                            self.terminal_process.stdin.write('\x1b[B')
                        self.terminal_process.stdin.flush()
                except Exception as e:
                    print(f"Error sending special key: {e}")

        @self.sio.event
        def change_directory(data):
            """Change current working directory"""
            path = data.get('path', '')
            try:
                # Clean the path first - remove double backslashes
                path = path.replace('\\\\', '\\').replace('//', '/')
                
                # Handle relative and absolute paths
                if os.path.isabs(path):
                    new_path = os.path.normpath(path)
                else:
                    new_path = os.path.normpath(os.path.join(self.current_directory, path))
                
                # Check if path exists
                if not os.path.exists(new_path):
                    raise FileNotFoundError(f"Path does not exist: {new_path}")
                
                if not os.path.isdir(new_path):
                    raise NotADirectoryError(f"Not a directory: {new_path}")
                
                os.chdir(new_path)
                self.current_directory = os.getcwd()
                
                # Restart terminal in new directory
                self.restart_terminal()
                
                self.sio.emit('directory_changed', {
                    'success': True,
                    'new_path': self.current_directory
                })
                
                # Automatically list the new directory
                self.list_directory_contents(self.current_directory)
                
            except Exception as e:
                self.sio.emit('directory_changed', {
                    'success': False,
                    'error': str(e),
                    'current_path': self.current_directory
                })

        @self.sio.event
        def list_directory(data):
            """List files in directory with enhanced info"""
            path = data.get('path', self.current_directory)
            self.list_directory_contents(path)

        @self.sio.event
        def navigate_up(data):
            """Navigate to parent directory"""
            try:
                parent = os.path.dirname(self.current_directory)
                if parent and parent != self.current_directory:
                    os.chdir(parent)
                    self.current_directory = os.getcwd()
                    self.restart_terminal()
                    
                    self.sio.emit('directory_changed', {
                        'success': True,
                        'new_path': self.current_directory
                    })
                    
                    self.list_directory_contents(self.current_directory)
            except Exception as e:
                self.sio.emit('directory_changed', {
                    'success': False,
                    'error': str(e)
                })

        @self.sio.event
        def upload_file(data):
            """Handle file upload from website"""
            try:
                filename = data.get('filename')
                content = data.get('content')
                path = data.get('path', self.current_directory)
                
                file_path = os.path.join(path, filename)
                
                # Decode base64 content
                file_content = base64.b64decode(content)
                
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                
                self.sio.emit('file_uploaded', {
                    'success': True,
                    'filename': filename,
                    'path': file_path,
                    'size': len(file_content)
                })
            except Exception as e:
                self.sio.emit('file_uploaded', {
                    'success': False,
                    'error': str(e)
                })

        @self.sio.event
        def download_file(data):
            """Send file or folder to website for download"""
            try:
                file_path = data.get('path')
                
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Path not found: {file_path}")
                
                # If it's a directory, create a zip file
                if os.path.isdir(file_path):
                    # Create a temporary zip file
                    import tempfile
                    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
                    temp_zip_path = temp_zip.name
                    temp_zip.close()
                    
                    # Zip the directory
                    shutil.make_archive(temp_zip_path[:-4], 'zip', file_path)
                    
                    # Read the zip file
                    with open(temp_zip_path, 'rb') as f:
                        content = f.read()
                    
                    # Clean up temp file
                    os.unlink(temp_zip_path)
                    
                    # Send the zip
                    encoded_content = base64.b64encode(content).decode()
                    
                    self.sio.emit('file_download', {
                        'success': True,
                        'filename': os.path.basename(file_path) + '.zip',
                        'content': encoded_content,
                        'size': len(content),
                        'is_folder': True
                    })
                else:
                    # Regular file download
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    encoded_content = base64.b64encode(content).decode()
                    
                    self.sio.emit('file_download', {
                        'success': True,
                        'filename': os.path.basename(file_path),
                        'content': encoded_content,
                        'size': len(content),
                        'is_folder': False
                    })
            except Exception as e:
                self.sio.emit('file_download', {
                    'success': False,
                    'error': str(e)
                })

        @self.sio.event
        def open_file(data):
            """Open file with default application"""
            try:
                file_path = data.get('path')
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"File not found: {file_path}")
                
                if platform.system() == "Windows":
                    os.startfile(file_path)
                else:
                    subprocess.Popen(['xdg-open', file_path])
                
                self.sio.emit('file_opened', {
                    'success': True,
                    'path': file_path
                })
            except Exception as e:
                self.sio.emit('file_opened', {
                    'success': False,
                    'error': str(e)
                })

        @self.sio.event
        def delete_file(data):
            """Delete file or directory"""
            try:
                path = data.get('path')
                
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                
                self.sio.emit('file_deleted', {
                    'success': True,
                    'path': path
                })
            except Exception as e:
                self.sio.emit('file_deleted', {
                    'success': False,
                    'error': str(e)
                })

        @self.sio.event
        def get_system_info(data):
            """Get detailed system information"""
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                network = psutil.net_io_counters()
                
                # Get GPU info if available
                gpu_info = "N/A"
                try:
                    import GPUtil
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu = gpus[0]
                        gpu_info = f"{gpu.name} - {gpu.load*100:.1f}% - {gpu.temperature}°C"
                except:
                    pass
                
                info = {
                    'cpu': {
                        'percent': cpu_percent,
                        'cores': psutil.cpu_count(),
                        'frequency': psutil.cpu_freq().current if psutil.cpu_freq() else 0
                    },
                    'memory': {
                        'total': memory.total,
                        'used': memory.used,
                        'percent': memory.percent
                    },
                    'disk': {
                        'total': disk.total,
                        'used': disk.used,
                        'free': disk.free,
                        'percent': disk.percent
                    },
                    'network': {
                        'bytes_sent': network.bytes_sent,
                        'bytes_recv': network.bytes_recv,
                        'packets_sent': network.packets_sent,
                        'packets_recv': network.packets_recv
                    },
                    'gpu': gpu_info,
                    'processes': len(psutil.pids()),
                    'boot_time': psutil.boot_time(),
                    'uptime': time.time() - psutil.boot_time()
                }
                
                self.sio.emit('system_info', {
                    'success': True,
                    'info': info
                })
            except Exception as e:
                self.sio.emit('system_info', {
                    'success': False,
                    'error': str(e)
                })

        @self.sio.event
        def start_system_monitoring(data):
            """Start continuous system monitoring"""
            self.send_system_stats = True
            if not self.system_stats_thread or not self.system_stats_thread.is_alive():
                self.system_stats_thread = threading.Thread(target=self.monitor_system_stats, daemon=True)
                self.system_stats_thread.start()

        @self.sio.event
        def stop_system_monitoring(data):
            """Stop system monitoring"""
            self.send_system_stats = False

        @self.sio.event
        def get_clipboard(data):
            """Get clipboard content"""
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                try:
                    clipboard_data = win32clipboard.GetClipboardData()
                    self.sio.emit('clipboard_content', {
                        'success': True,
                        'content': clipboard_data
                    })
                except:
                    self.sio.emit('clipboard_content', {
                        'success': True,
                        'content': ''
                    })
                finally:
                    win32clipboard.CloseClipboard()
            except Exception as e:
                self.sio.emit('clipboard_content', {
                    'success': False,
                    'error': str(e)
                })

        @self.sio.event
        def set_clipboard(data):
            """Set clipboard content"""
            try:
                import win32clipboard
                content = data.get('content', '')
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(content)
                win32clipboard.CloseClipboard()
                self.sio.emit('clipboard_set', {'success': True})
            except Exception as e:
                self.sio.emit('clipboard_set', {
                    'success': False,
                    'error': str(e)
                })

        # Keep existing handlers for screenshots, mouse, keyboard, processes...
        @self.sio.event
        def take_screenshot(data):
            """Enhanced screenshot with options"""
            try:
                monitor = data.get('monitor', 0)  # Support multi-monitor
                quality = data.get('quality', 85)
                
                screenshot = ImageGrab.grab()
                
                # Apply any filters if requested
                if data.get('grayscale'):
                    screenshot = screenshot.convert('L')
                
                buffer = io.BytesIO()
                screenshot.save(buffer, format='PNG', optimize=True, quality=quality)
                screenshot_data = base64.b64encode(buffer.getvalue()).decode()

                self.sio.emit('screenshot_result', {
                    'success': True,
                    'data': screenshot_data,
                    'timestamp': time.time(),
                    'resolution': screenshot.size
                })
            except Exception as e:
                self.sio.emit('screenshot_result', {
                    'success': False,
                    'error': str(e)
                })

        @self.sio.event
        def start_live_monitoring(data):
            """Start enhanced live screen monitoring"""
            self.live_monitoring = True
            quality = data.get('quality', 60)
            fps = data.get('fps', 10)
            threading.Thread(target=self.enhanced_live_monitor, args=(quality, fps), daemon=True).start()

        @self.sio.event
        def stop_live_monitoring(data):
            """Stop live screen monitoring"""
            self.live_monitoring = False

    def start_enhanced_terminal(self):
        """Start enhanced terminal with real-time output streaming"""
        try:
            if platform.system() == "Windows":
                # Create a new CMD process with proper flags for real-time interaction
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                self.terminal_process = subprocess.Popen(
                    'cmd.exe',
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=0,
                    cwd=self.current_directory,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    startupinfo=startupinfo
                )
            else:
                # Unix-like systems
                self.terminal_process = subprocess.Popen(
                    ['/bin/bash', '-i'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=0,
                    cwd=self.current_directory,
                    preexec_fn=os.setsid
                )
            
            # Start output reader thread
            self.terminal_thread = threading.Thread(target=self.read_terminal_output, daemon=True)
            self.terminal_thread.start()
            
            # Start command processor thread
            threading.Thread(target=self.process_commands, daemon=True).start()
            
            print("✅ Enhanced terminal started successfully")
            
        except Exception as e:
            print(f"❌ Failed to start terminal: {e}")

    def read_terminal_output(self):
        """Read terminal output in real-time and send to website"""
        line_buffer = ""
        while self.running and self.terminal_process:
            try:
                if self.terminal_process.poll() is not None:
                    # Terminal process ended, restart it
                    self.restart_terminal()
                    continue
                
                # Read output character by character but buffer until newline
                output_char = self.terminal_process.stdout.read(1)
                if output_char:
                    line_buffer += output_char
                    
                    # Send complete lines or after certain characters
                    if output_char in ['\n', '\r'] or len(line_buffer) > 100:
                        if line_buffer.strip():  # Only send non-empty lines
                            # Send to website
                            if self.sio.connected:
                                self.sio.emit('terminal_output', {
                                    'data': line_buffer,
                                    'type': 'stream',
                                    'timestamp': time.time()
                                })
                            
                            # Add to buffer
                            self.terminal_buffer.append(line_buffer)
                            if len(self.terminal_buffer) > self.max_buffer_size:
                                self.terminal_buffer = self.terminal_buffer[-self.max_buffer_size:]
                        
                        line_buffer = ""
                
                time.sleep(0.001)  # Small delay to prevent CPU overuse
                
            except Exception as e:
                print(f"Error reading terminal output: {e}")
                time.sleep(0.1)

    def process_commands(self):
        """Process commands from the queue"""
        while self.running:
            try:
                if not self.command_queue.empty():
                    command = self.command_queue.get()
                    
                    if self.terminal_process and self.terminal_process.poll() is None:
                        # Send command to terminal
                        self.terminal_process.stdin.write(command + '\n')
                        self.terminal_process.stdin.flush()
                        
                        # Echo the command back to website
                        self.sio.emit('terminal_output', {
                            'data': f"> {command}\n",
                            'type': 'command',
                            'timestamp': time.time()
                        })
                
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Error processing command: {e}")
                time.sleep(0.1)

    def restart_terminal(self):
        """Restart the terminal process"""
        try:
            if self.terminal_process:
                self.terminal_process.terminate()
                time.sleep(0.5)
                if self.terminal_process.poll() is None:
                    self.terminal_process.kill()
            
            self.start_enhanced_terminal()
            
            # Notify website
            self.sio.emit('terminal_restarted', {
                'cwd': self.current_directory
            })
            
        except Exception as e:
            print(f"Error restarting terminal: {e}")

    def monitor_system_stats(self):
        """Continuously monitor and send system stats"""
        while self.send_system_stats and self.running:
            try:
                stats = {
                    'cpu': psutil.cpu_percent(interval=1),
                    'memory': psutil.virtual_memory().percent,
                    'disk': psutil.disk_usage('/').percent,
                    'network': {
                        'sent': psutil.net_io_counters().bytes_sent,
                        'recv': psutil.net_io_counters().bytes_recv
                    },
                    'timestamp': time.time()
                }
                
                if self.sio.connected:
                    self.sio.emit('system_stats_update', stats)
                
                time.sleep(2)  # Update every 2 seconds
                
            except Exception as e:
                print(f"Error monitoring system: {e}")
                time.sleep(5)

    def enhanced_live_monitor(self, quality=60, fps=10):
        """Enhanced live monitoring with better compression and performance"""
        frame_interval = 1.0 / fps
        last_frame_time = 0
        
        while self.live_monitoring and self.running:
            try:
                current_time = time.time()
                
                if current_time - last_frame_time < frame_interval:
                    time.sleep(0.01)
                    continue
                
                if not self.sio.connected:
                    self.live_monitoring = False
                    break
                
                # Capture screen
                screenshot = ImageGrab.grab()
                
                # Dynamic quality adjustment based on network speed
                width, height = screenshot.size
                if width > 1920:
                    new_width = 1920
                    new_height = int(height * (new_width / width))
                    screenshot = screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Convert to JPEG for better compression
                buffer = io.BytesIO()
                screenshot.save(buffer, format='JPEG', quality=quality, optimize=True)
                frame_data = base64.b64encode(buffer.getvalue()).decode()
                
                if self.sio.connected:
                    self.sio.emit('live_frame', {
                        'data': frame_data,
                        'width': screenshot.size[0],
                        'height': screenshot.size[1],
                        'timestamp': current_time
                    })
                
                last_frame_time = current_time
                
            except Exception as e:
                print(f"Live monitoring error: {e}")
                time.sleep(1)

    def list_directory_contents(self, path):
        """Helper method to list directory contents"""
        try:
            items = []
            # Clean the path first
            path = os.path.normpath(path)
            
            # List all items in the directory
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                try:
                    stat = os.stat(item_path)
                    items.append({
                        'name': item,
                        'type': 'dir' if os.path.isdir(item_path) else 'file',
                        'size': stat.st_size if not os.path.isdir(item_path) else 0,
                        'modified': stat.st_mtime,
                        'permissions': oct(stat.st_mode)[-3:],
                        'full_path': os.path.normpath(item_path)  # Normalized path
                    })
                except Exception as e:
                    # Skip items we can't stat
                    continue
            
            # Sort: directories first, then files, alphabetically
            items.sort(key=lambda x: (x['type'] != 'dir', x['name'].lower()))
            
            self.sio.emit('directory_listing', {
                'success': True,
                'path': path,
                'items': items,
                'parent': os.path.dirname(path) if path != os.path.dirname(path) else None
            })
        except Exception as e:
            self.sio.emit('directory_listing', {
                'success': False,
                'error': str(e),
                'path': path
            })
        """Gracefully stop the client"""
        print("\n🛑 Shutting down enhanced local client...")
        self.running = False
        self.live_monitoring = False
        self.send_system_stats = False

        # Clean up terminal process
        if self.terminal_process:
            try:
                self.terminal_process.terminate()
                self.terminal_process.wait(timeout=5)
            except:
                try:
                    self.terminal_process.kill()
                except:
                    pass

        try:
            if self.sio.connected:
                self.sio.disconnect()
        except:
            pass

        print("✅ Local client stopped.")
        sys.exit(0)

    def connect_with_retry(self):
        """Enhanced connection with retry logic"""
        if self.start_time is None:
            self.start_time = time.time()

        retry_count = 0
        while self.running:
            elapsed_time = time.time() - self.start_time
            if elapsed_time >= self.max_reconnect_duration:
                print("⏰ 24 hours have passed. Stopping reconnection attempts.")
                break

            try:
                remaining_time = self.max_reconnect_duration - elapsed_time
                hours_left = int(remaining_time // 3600)
                minutes_left = int((remaining_time % 3600) // 60)
                
                print(f"🔄 Connecting to {self.server_url}... (Attempt #{retry_count + 1})")
                print(f"⏱️ Will keep trying for {hours_left}h {minutes_left}m more...")

                self.sio.connect(self.server_url, transports=['websocket'])
                retry_count = 0  # Reset on successful connection

                while self.running and self.sio.connected:
                    time.sleep(1)

                if not self.running:
                    break

            except KeyboardInterrupt:
                print("\n⌨️ Ctrl+C detected. Stopping client...")
                self.stop()
                break
            except Exception as e:
                if not self.running:
                    break
                retry_count += 1
                print(f"❌ Connection error: {e}")
                
                # Progressive backoff
                wait_time = min(5 * (1 + retry_count * 0.5), 60)
                print(f"⏳ Retrying in {wait_time:.0f} seconds...")
                
                for i in range(int(wait_time)):
                    if not self.running:
                        break
                    time.sleep(1)

def signal_handler(sig, frame):
    """Handle Ctrl+C signal"""
    print("\n⌨️ Ctrl+C detected. Shutting down...")
    if 'client' in globals():
        client.stop()
    else:
        sys.exit(0)

def main():
    global client
    server_url = "https://netbit.onrender.com"

    print("🚀 Starting Enhanced Local Client v2.0")
    print("=" * 50)
    print("Features:")
    print("  ✅ Real-time bidirectional terminal")
    print("  ✅ File management system")
    print("  ✅ System monitoring")
    print("  ✅ Enhanced live screen sharing")
    print("  ✅ Clipboard synchronization")
    print("  ✅ Process management")
    print("=" * 50)
    
    client = EnhancedLocalClient(server_url)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        client.connect_with_retry()
    except KeyboardInterrupt:
        print("\n⌨️ Ctrl+C detected. Shutting down...")
        client.stop()

if __name__ == "__main__":
    print("Enhanced Remote Terminal Client v2.0")
    print("Press Ctrl+C to stop the client at any time.\n")

    if platform.system() == "Windows":
        if not is_admin():
            print("⚠️ This script requires administrator privileges.")
            print("🔄 Attempting to restart with administrator privileges...")
            if not run_as_admin():
                sys.exit(1)
        else:
            print("✅ Running with administrator privileges\n")

    try:
        main()
    except KeyboardInterrupt:
        print("\n⌨️ Ctrl+C detected. Exiting...")
        sys.exit(0)
