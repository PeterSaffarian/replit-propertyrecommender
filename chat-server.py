#!/usr/bin/env python3
"""
Real-time chat interface for property_recommender.orchestrator
Pipes the actual CLI conversation through a web interface
"""

import asyncio
import json
import subprocess
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
import os

class ChatHandler(SimpleHTTPRequestHandler):
    orchestrator_process = None
    chat_history = []
    waiting_for_input = False
    current_question = ""
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.serve_chat_interface()
        elif self.path == '/api/messages':
            self.serve_json({'messages': ChatHandler.chat_history, 'waiting': ChatHandler.waiting_for_input, 'question': ChatHandler.current_question})
        elif self.path.startswith('/api/'):
            self.send_error(404)
        else:
            super().do_GET()
    
    def do_POST(self):
        if self.path == '/api/start':
            self.start_orchestrator()
        elif self.path == '/api/send':
            self.handle_user_input()
        else:
            self.send_error(404)
    
    def serve_chat_interface(self):
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Property Recommender</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; height: 100vh; display: flex; flex-direction: column; }
        .header { background: white; padding: 1rem; border-bottom: 1px solid #e0e0e0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .header h1 { color: #333; font-size: 1.5rem; }
        .chat-container { flex: 1; display: flex; flex-direction: column; max-width: 800px; margin: 0 auto; width: 100%; }
        .messages { flex: 1; overflow-y: auto; padding: 1rem; }
        .message { margin-bottom: 1rem; display: flex; }
        .message.user { justify-content: flex-end; }
        .message.assistant { justify-content: flex-start; }
        .message-bubble { max-width: 70%; padding: 0.75rem 1rem; border-radius: 1rem; }
        .message.user .message-bubble { background: #007bff; color: white; }
        .message.assistant .message-bubble { background: white; color: #333; border: 1px solid #e0e0e0; }
        .input-area { background: white; padding: 1rem; border-top: 1px solid #e0e0e0; }
        .input-container { display: flex; gap: 0.5rem; }
        .input-container input { flex: 1; padding: 0.75rem; border: 1px solid #ddd; border-radius: 0.5rem; font-size: 1rem; }
        .input-container input:focus { outline: none; border-color: #007bff; }
        .input-container button { padding: 0.75rem 1.5rem; background: #007bff; color: white; border: none; border-radius: 0.5rem; cursor: pointer; font-size: 1rem; }
        .input-container button:hover { background: #0056b3; }
        .input-container button:disabled { background: #ccc; cursor: not-allowed; }
        .start-button { background: #28a745; margin-bottom: 1rem; }
        .start-button:hover { background: #1e7e34; }
        .timestamp { font-size: 0.75rem; opacity: 0.6; margin-top: 0.25rem; }
        .waiting { font-style: italic; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏠 Property Recommender</h1>
    </div>
    
    <div class="chat-container">
        <div id="messages" class="messages">
            <div class="message assistant">
                <div class="message-bubble">
                    Welcome! I'm your property recommendation assistant. Click "Start" to begin finding your perfect property.
                    <div class="timestamp">${new Date().toLocaleTimeString()}</div>
                </div>
            </div>
        </div>
        
        <div class="input-area">
            <button id="start-btn" onclick="startChat()" class="input-container button start-button" style="width: 100%; margin-bottom: 1rem;">
                🚀 Start Property Search
            </button>
            
            <div class="input-container">
                <input id="user-input" type="text" placeholder="Type your response here..." disabled>
                <button id="send-btn" onclick="sendMessage()" disabled>Send</button>
            </div>
        </div>
    </div>

    <script>
        let isStarted = false;
        let polling = false;
        
        function addMessage(content, isUser = false) {
            const messages = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
            messageDiv.innerHTML = `
                <div class="message-bubble">
                    ${content}
                    <div class="timestamp">${new Date().toLocaleTimeString()}</div>
                </div>
            `;
            messages.appendChild(messageDiv);
            messages.scrollTop = messages.scrollHeight;
        }
        
        async function startChat() {
            document.getElementById('start-btn').style.display = 'none';
            isStarted = true;
            
            try {
                const response = await fetch('/api/start', { method: 'POST' });
                if (response.ok) {
                    addMessage('Starting the property recommendation process...', false);
                    startPolling();
                } else {
                    addMessage('Error starting the process. Please check your API credentials.', false);
                }
            } catch (error) {
                addMessage('Connection error. Please try again.', false);
            }
        }
        
        async function sendMessage() {
            const input = document.getElementById('user-input');
            const message = input.value.trim();
            
            if (!message) return;
            
            addMessage(message, true);
            input.value = '';
            input.disabled = true;
            document.getElementById('send-btn').disabled = true;
            
            try {
                const response = await fetch('/api/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message })
                });
            } catch (error) {
                addMessage('Error sending message.', false);
            }
        }
        
        function startPolling() {
            if (polling) return;
            polling = true;
            pollMessages();
        }
        
        async function pollMessages() {
            try {
                const response = await fetch('/api/messages');
                const data = await response.json();
                
                // Add any new messages
                data.messages.forEach(msg => {
                    if (!msg.displayed) {
                        addMessage(msg.content, msg.isUser);
                        msg.displayed = true;
                    }
                });
                
                // Handle input state
                const input = document.getElementById('user-input');
                const sendBtn = document.getElementById('send-btn');
                
                if (data.waiting) {
                    input.disabled = false;
                    sendBtn.disabled = false;
                    input.focus();
                    input.placeholder = data.question || "Type your response...";
                } else {
                    input.disabled = true;
                    sendBtn.disabled = true;
                    input.placeholder = "Waiting for next question...";
                }
                
                if (polling) {
                    setTimeout(pollMessages, 1000);
                }
            } catch (error) {
                console.error('Polling error:', error);
                if (polling) {
                    setTimeout(pollMessages, 2000);
                }
            }
        }
        
        document.getElementById('user-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    </script>
</body>
</html>"""
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def serve_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def start_orchestrator(self):
        if ChatHandler.orchestrator_process and ChatHandler.orchestrator_process.poll() is None:
            self.serve_json({'error': 'Process already running'})
            return
        
        ChatHandler.chat_history = []
        ChatHandler.waiting_for_input = False
        
        def run_process():
            try:
                ChatHandler.orchestrator_process = subprocess.Popen(
                    [sys.executable, '-m', 'property_recommender.orchestrator'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Read output line by line
                while True:
                    line = ChatHandler.orchestrator_process.stdout.readline()
                    if not line:
                        break
                    
                    line = line.strip()
                    if not line:
                        continue
                    
                    print(f"Orchestrator output: {line}")
                    
                    # Check if this is a question (ends with "?")
                    if line.endswith('?') or 'You:' in line:
                        ChatHandler.current_question = line.replace('You:', '').strip()
                        ChatHandler.waiting_for_input = True
                        if not line.startswith('You:'):
                            ChatHandler.chat_history.append({
                                'content': line,
                                'isUser': False,
                                'displayed': False
                            })
                    else:
                        # Regular output
                        ChatHandler.chat_history.append({
                            'content': line,
                            'isUser': False,
                            'displayed': False
                        })
                
            except Exception as e:
                print(f"Error running orchestrator: {e}")
                ChatHandler.chat_history.append({
                    'content': f'Error: {str(e)}',
                    'isUser': False,
                    'displayed': False
                })
        
        thread = threading.Thread(target=run_process)
        thread.daemon = True
        thread.start()
        
        self.serve_json({'message': 'Process started'})
    
    def handle_user_input(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        user_message = data.get('message', '')
        
        # Add user message to history
        ChatHandler.chat_history.append({
            'content': user_message,
            'isUser': True,
            'displayed': False
        })
        
        # Send to orchestrator
        if ChatHandler.orchestrator_process and ChatHandler.orchestrator_process.poll() is None:
            try:
                ChatHandler.orchestrator_process.stdin.write(user_message + '\n')
                ChatHandler.orchestrator_process.stdin.flush()
                ChatHandler.waiting_for_input = False
            except Exception as e:
                print(f"Error sending input: {e}")
        
        self.serve_json({'status': 'sent'})

def main():
    port = 8080
    server_address = ('0.0.0.0', port)
    
    print("🚀 Property Recommender Chat Interface")
    print(f"🌐 Open: http://localhost:{port}")
    print("💬 Direct connection to your Python orchestrator!")
    print("=" * 50)
    
    httpd = HTTPServer(server_address, ChatHandler)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        if ChatHandler.orchestrator_process:
            ChatHandler.orchestrator_process.terminate()
        httpd.shutdown()

if __name__ == '__main__':
    main()