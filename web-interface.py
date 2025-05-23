#!/usr/bin/env python3
"""
Simple web interface for the property recommendation system.
This wraps around your existing orchestrator.py without modifying it.
"""

import json
import subprocess
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os
import sys

class PropertyRecommenderHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.process_status = {
            'steps': [
                {'id': 'profile', 'name': 'Collecting your preferences', 'status': 'pending', 'output': []},
                {'id': 'gathering', 'name': 'Finding properties on Trade Me', 'status': 'pending', 'output': []},
                {'id': 'matching', 'name': 'Analyzing matches for you', 'status': 'pending', 'output': []}
            ],
            'isRunning': False
        }
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/':
            self.serve_index()
        elif parsed_path.path == '/api/status':
            self.serve_json(self.process_status)
        elif parsed_path.path == '/api/results':
            self.serve_results()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/start-recommendation':
            self.start_recommendation()
        else:
            self.send_error(404)

    def serve_index(self):
        html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Property Recommender</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        .animate-spin { animation: spin 1s linear infinite; }
    </style>
</head>
<body class="bg-gray-50">
    <div class="min-h-screen flex">
        <!-- Sidebar -->
        <div class="w-64 bg-white shadow-lg">
            <div class="p-6 border-b">
                <h1 class="text-xl font-bold text-gray-900">🏠 Property Finder</h1>
            </div>
            <div class="p-4">
                <h3 class="text-sm font-semibold text-gray-600 mb-3">Process Steps</h3>
                <div id="steps-container">
                    <!-- Steps will be populated here -->
                </div>
            </div>
        </div>

        <!-- Main Chat Area -->
        <div class="flex-1 flex flex-col">
            <div class="bg-white shadow-sm border-b p-4">
                <div class="flex items-center justify-between">
                    <h2 class="text-lg font-semibold text-gray-900">💬 Property Recommendation Chat</h2>
                    <button id="start-btn" onclick="startRecommendation()" 
                            class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors">
                        ▶️ Start Finding Properties
                    </button>
                </div>
            </div>

            <!-- Messages -->
            <div id="messages" class="flex-1 overflow-y-auto p-6 space-y-4">
                <div class="flex justify-start">
                    <div class="bg-white text-gray-900 shadow-sm border px-4 py-2 rounded-lg max-w-md">
                        <p class="text-sm">Welcome! I'm your property recommendation assistant. I'll help you find the perfect property by understanding your preferences and searching Trade Me for the best matches.</p>
                        <p class="text-xs opacity-70 mt-1" id="welcome-time"></p>
                    </div>
                </div>
            </div>

            <!-- Results Display -->
            <div id="results-section" class="bg-white border-t p-6 hidden">
                <h3 class="text-lg font-semibold mb-4">Your Property Recommendations</h3>
                <div id="results-container"></div>
            </div>
        </div>
    </div>

    <script>
        let isStarted = false;
        let pollInterval = null;

        // Set welcome message time
        document.getElementById('welcome-time').textContent = new Date().toLocaleTimeString();

        function addMessage(role, content) {
            const messagesContainer = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'}`;
            
            const contentClass = role === 'user' 
                ? 'bg-blue-600 text-white' 
                : role === 'system' 
                ? 'bg-gray-100 text-gray-700 text-sm'
                : 'bg-white text-gray-900 shadow-sm border';

            messageDiv.innerHTML = `
                <div class="${contentClass} px-4 py-2 rounded-lg max-w-md">
                    <p class="text-sm">${content}</p>
                    <p class="text-xs opacity-70 mt-1">${new Date().toLocaleTimeString()}</p>
                </div>
            `;
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        function getStepIcon(status) {
            switch(status) {
                case 'running': return '<div class="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>';
                case 'completed': return '<div class="w-4 h-4 bg-green-500 rounded-full flex items-center justify-center text-white text-xs">✓</div>';
                case 'error': return '<div class="w-4 h-4 bg-red-500 rounded-full flex items-center justify-center text-white text-xs">✗</div>';
                default: return '<div class="w-4 h-4 bg-gray-400 rounded-full"></div>';
            }
        }

        function updateSteps(steps) {
            const container = document.getElementById('steps-container');
            container.innerHTML = steps.map(step => `
                <div class="flex items-center space-x-3 p-2 rounded-lg mb-2">
                    ${getStepIcon(step.status)}
                    <span class="text-sm text-gray-700">${step.name}</span>
                </div>
            `).join('');
        }

        async function startRecommendation() {
            if (isStarted) return;
            
            isStarted = true;
            document.getElementById('start-btn').style.display = 'none';
            
            addMessage('assistant', 'Great! Let me start the property recommendation process for you. This will happen in three main steps:');
            addMessage('assistant', '1. First, I\\'ll collect your property preferences through a conversation');
            addMessage('assistant', '2. Then, I\\'ll search Trade Me for properties that match your criteria');
            addMessage('assistant', '3. Finally, I\\'ll analyze and rank the best matches for you');
            addMessage('assistant', 'Starting the process now...');

            try {
                const response = await fetch('/api/start-recommendation', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    pollStatus();
                } else {
                    addMessage('assistant', 'Sorry, I encountered an error starting the process. Please make sure all API credentials are properly configured.');
                    isStarted = false;
                    document.getElementById('start-btn').style.display = 'block';
                }
            } catch (error) {
                addMessage('assistant', 'Connection error. Please make sure the server is running and try again.');
                isStarted = false;
                document.getElementById('start-btn').style.display = 'block';
            }
        }

        let lastStepStatuses = {};

        async function pollStatus() {
            try {
                const response = await fetch('/api/status');
                const status = await response.json();
                
                updateSteps(status.steps);
                
                // Update messages based on step progress
                status.steps.forEach(step => {
                    if (lastStepStatuses[step.id] !== step.status) {
                        if (step.status === 'running') {
                            addMessage('system', `🔄 ${step.name}...`);
                        } else if (step.status === 'completed') {
                            addMessage('system', `✅ ${step.name} - Complete!`);
                        } else if (step.status === 'error' && step.error) {
                            addMessage('system', `❌ Error in ${step.name}: ${step.error}`);
                        }
                        lastStepStatuses[step.id] = step.status;
                    }
                });

                if (status.isRunning) {
                    setTimeout(pollStatus, 2000);
                } else {
                    fetchResults();
                }
            } catch (error) {
                console.error('Error polling status:', error);
                setTimeout(pollStatus, 5000);
            }
        }

        async function fetchResults() {
            try {
                const response = await fetch('/api/results');
                if (response.ok) {
                    const results = await response.json();
                    displayResults(results);
                    addMessage('assistant', 'Perfect! I\\'ve found and analyzed your property matches. Here are your personalized recommendations:');
                }
            } catch (error) {
                addMessage('assistant', 'The process completed, but I\\'m having trouble loading the final results. Please check that all steps completed successfully.');
            }
        }

        function displayResults(results) {
            const resultsSection = document.getElementById('results-section');
            const resultsContainer = document.getElementById('results-container');
            
            if (Array.isArray(results) && results.length > 0) {
                resultsContainer.innerHTML = results.slice(0, 5).map((property, index) => `
                    <div class="border rounded-lg p-4 hover:shadow-md transition-shadow mb-4">
                        <div class="flex justify-between items-start mb-2">
                            <h4 class="font-semibold text-gray-900">Property #${property.property_id || index + 1}</h4>
                            <span class="bg-green-100 text-green-800 px-2 py-1 rounded text-sm">
                                Score: ${property.score || 'N/A'}/10
                            </span>
                        </div>
                        <p class="text-gray-600 text-sm mb-2">${property.rationale || 'Analysis complete'}</p>
                    </div>
                `).join('');
                resultsSection.classList.remove('hidden');
            } else {
                resultsContainer.innerHTML = '<p class="text-gray-600">Results are being processed...</p>';
                resultsSection.classList.remove('hidden');
            }
        }
    </script>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode())

    def serve_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def serve_results(self):
        try:
            if os.path.exists('property_matches.json'):
                with open('property_matches.json', 'r') as f:
                    results = json.load(f)
                self.serve_json(results)
            else:
                self.send_error(404, 'Results not yet available')
        except Exception as e:
            self.send_error(500, f'Failed to read results: {str(e)}')

    def start_recommendation(self):
        if PropertyRecommenderHandler.process_status.get('isRunning', False):
            self.serve_json({'error': 'Process already running'})
            return

        # Reset process state
        PropertyRecommenderHandler.process_status = {
            'steps': [
                {'id': 'profile', 'name': 'Collecting your preferences', 'status': 'pending', 'output': []},
                {'id': 'gathering', 'name': 'Finding properties on Trade Me', 'status': 'pending', 'output': []},
                {'id': 'matching', 'name': 'Analyzing matches for you', 'status': 'pending', 'output': []}
            ],
            'isRunning': True
        }

        # Start the Python orchestrator in a separate thread
        def run_orchestrator():
            try:
                print("Starting property recommendation orchestrator...")
                PropertyRecommenderHandler.process_status['steps'][0]['status'] = 'running'
                
                result = subprocess.run([
                    sys.executable, '-m', 'property_recommender.orchestrator'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("Orchestrator completed successfully")
                    for step in PropertyRecommenderHandler.process_status['steps']:
                        if step['status'] != 'error':
                            step['status'] = 'completed'
                else:
                    print(f"Orchestrator failed with error: {result.stderr}")
                    PropertyRecommenderHandler.process_status['steps'][0]['status'] = 'error'
                    PropertyRecommenderHandler.process_status['steps'][0]['error'] = result.stderr
                    
            except Exception as e:
                print(f"Error running orchestrator: {e}")
                PropertyRecommenderHandler.process_status['steps'][0]['status'] = 'error'
                PropertyRecommenderHandler.process_status['steps'][0]['error'] = str(e)
            finally:
                PropertyRecommenderHandler.process_status['isRunning'] = False

        thread = threading.Thread(target=run_orchestrator)
        thread.daemon = True
        thread.start()

        self.serve_json({'message': 'Process started', 'status': PropertyRecommenderHandler.process_status})

# Global process status (shared across all request instances)
PropertyRecommenderHandler.process_status = {
    'steps': [
        {'id': 'profile', 'name': 'Collecting your preferences', 'status': 'pending', 'output': []},
        {'id': 'gathering', 'name': 'Finding properties on Trade Me', 'status': 'pending', 'output': []},
        {'id': 'matching', 'name': 'Analyzing matches for you', 'status': 'pending', 'output': []}
    ],
    'isRunning': False
}

def main():
    port = 8080
    server_address = ('0.0.0.0', port)
    
    print("🚀 Property Recommender Web Interface")
    print(f"🌐 Open your browser and visit: http://localhost:{port}")
    print("📱 Click 'Start Finding Properties' to begin!")
    print("=" * 50)
    
    httpd = HTTPServer(server_address, PropertyRecommenderHandler)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down web interface...")
        httpd.shutdown()

if __name__ == '__main__':
    main()