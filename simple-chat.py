#!/usr/bin/env python3
"""
Simple web chat interface for property_recommender.orchestrator
"""

import subprocess
import threading
import time
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs
import sys
import queue

class SimpleChatHandler(SimpleHTTPRequestHandler):
    # Shared state
    process = None
    input_queue = queue.Queue()
    output_queue = queue.Queue()
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.serve_chat_page()
        elif self.path == '/api/poll':
            self.handle_poll()
        else:
            self.send_error(404)
    
    def do_POST(self):
        if self.path == '/api/start':
            self.start_chat()
        elif self.path == '/api/send':
            self.handle_send()
        else:
            self.send_error(404)
    
    def serve_chat_page(self):
        html = '''<!DOCTYPE html>
<html>
<head>
    <title>Property Chat</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: #007bff; color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center; }
        .chat { height: 400px; overflow-y: auto; padding: 20px; border-bottom: 1px solid #eee; }
        .message { margin: 10px 0; padding: 10px; border-radius: 5px; }
        .assistant { background: #f1f1f1; }
        .user { background: #007bff; color: white; text-align: right; }
        .input-area { padding: 20px; }
        .input-area input { width: 70%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        .input-area button { width: 25%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; margin-left: 10px; cursor: pointer; }
        .input-area button:disabled { background: #ccc; cursor: not-allowed; }
        .start-btn { width: 100%; padding: 15px; background: #28a745; color: white; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Property Recommender</h1>
        </div>
        <div class="chat" id="chat">
            <div class="message assistant">Welcome! Click Start to begin your property search.</div>
        </div>
        <div class="input-area">
            <button id="startBtn" class="start-btn" onclick="startChat()">Start Property Search</button>
            <div id="inputDiv" style="display:none;">
                <input type="text" id="messageInput" placeholder="Type your response..." onkeypress="if(event.key==='Enter')sendMessage()">
                <button onclick="sendMessage()" id="sendBtn">Send</button>
            </div>
        </div>
    </div>

    <script>
        let started = false;
        
        function addMessage(text, isUser = false) {
            const chat = document.getElementById('chat');
            const div = document.createElement('div');
            div.className = 'message ' + (isUser ? 'user' : 'assistant');
            div.textContent = text;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }
        
        async function startChat() {
            if (started) return;
            started = true;
            
            document.getElementById('startBtn').style.display = 'none';
            document.getElementById('inputDiv').style.display = 'block';
            
            addMessage('Starting property recommendation system...');
            
            try {
                await fetch('/api/start', { method: 'POST' });
                pollForMessages();
            } catch (error) {
                addMessage('Error starting system. Please check your setup.');
            }
        }
        
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;
            
            addMessage(message, true);
            input.value = '';
            
            try {
                await fetch('/api/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message })
                });
            } catch (error) {
                addMessage('Error sending message.');
            }
        }
        
        async function pollForMessages() {
            try {
                const response = await fetch('/api/poll');
                const data = await response.json();
                
                if (data.messages) {
                    data.messages.forEach(msg => addMessage(msg));
                }
                
                if (started) {
                    setTimeout(pollForMessages, 1000);
                }
            } catch (error) {
                console.error('Poll error:', error);
                if (started) {
                    setTimeout(pollForMessages, 2000);
                }
            }
        }
    </script>
</body>
</html>'''
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def start_chat(self):
        if SimpleChatHandler.process:
            self.send_json({'error': 'Already running'})
            return
        
        def run_orchestrator():
            try:
                SimpleChatHandler.process = subprocess.Popen(
                    [sys.executable, '-m', 'property_recommender.orchestrator'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                # Read input thread
                def handle_input():
                    while SimpleChatHandler.process and SimpleChatHandler.process.poll() is None:
                        try:
                            user_input = SimpleChatHandler.input_queue.get(timeout=1)
                            SimpleChatHandler.process.stdin.write(user_input + '\n')
                            SimpleChatHandler.process.stdin.flush()
                        except queue.Empty:
                            continue
                        except:
                            break
                
                # Read output thread
                def handle_output():
                    while SimpleChatHandler.process and SimpleChatHandler.process.poll() is None:
                        try:
                            line = SimpleChatHandler.process.stdout.readline()
                            if line:
                                line = line.strip()
                                if line and not line.startswith('INFO:') and not line.startswith('You:'):
                                    SimpleChatHandler.output_queue.put(line)
                        except:
                            break
                
                input_thread = threading.Thread(target=handle_input)
                output_thread = threading.Thread(target=handle_output)
                input_thread.daemon = True
                output_thread.daemon = True
                input_thread.start()
                output_thread.start()
                
                SimpleChatHandler.process.wait()
                
            except Exception as e:
                SimpleChatHandler.output_queue.put(f"Error: {str(e)}")
        
        thread = threading.Thread(target=run_orchestrator)
        thread.daemon = True
        thread.start()
        
        self.send_json({'status': 'started'})
    
    def handle_send(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        message = data.get('message', '')
        SimpleChatHandler.input_queue.put(message)
        
        self.send_json({'status': 'sent'})
    
    def handle_poll(self):
        messages = []
        while not SimpleChatHandler.output_queue.empty():
            try:
                messages.append(SimpleChatHandler.output_queue.get_nowait())
            except queue.Empty:
                break
        
        self.send_json({'messages': messages})
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

if __name__ == '__main__':
    port = 8080
    print(f"🚀 Simple Property Chat: http://localhost:{port}")
    
    httpd = HTTPServer(('0.0.0.0', port), SimpleChatHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        if SimpleChatHandler.process:
            SimpleChatHandler.process.terminate()