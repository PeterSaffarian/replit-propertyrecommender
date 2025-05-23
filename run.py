#!/usr/bin/env python3
"""
Simple web server for the property recommendation interface
"""
import http.server
import socketserver
import os
import sys

class PropertyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Property Recommender</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <div class="max-w-4xl mx-auto">
            <!-- Header -->
            <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
                <div class="flex items-center justify-between">
                    <div>
                        <h1 class="text-2xl font-bold text-gray-900">🏠 Property Recommendation System</h1>
                        <p class="text-gray-600 mt-1">Find your perfect property with AI-powered recommendations</p>
                    </div>
                    <button id="start-btn" onclick="startProcess()" 
                            class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium transition-colors">
                        🚀 Start Finding Properties
                    </button>
                </div>
            </div>

            <!-- Process Steps -->
            <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
                <h2 class="text-lg font-semibold text-gray-900 mb-4">How it works</h2>
                <div class="space-y-4">
                    <div id="step1" class="flex items-center space-x-3 p-3 rounded-lg bg-gray-50">
                        <div class="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center text-white font-bold">1</div>
                        <div>
                            <h3 class="font-medium text-gray-900">Collect Your Preferences</h3>
                            <p class="text-sm text-gray-600">Interactive conversation to understand what you're looking for</p>
                        </div>
                    </div>
                    
                    <div id="step2" class="flex items-center space-x-3 p-3 rounded-lg bg-gray-50">
                        <div class="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center text-white font-bold">2</div>
                        <div>
                            <h3 class="font-medium text-gray-900">Search Trade Me Properties</h3>
                            <p class="text-sm text-gray-600">Find available properties that match your criteria</p>
                        </div>
                    </div>
                    
                    <div id="step3" class="flex items-center space-x-3 p-3 rounded-lg bg-gray-50">
                        <div class="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center text-white font-bold">3</div>
                        <div>
                            <h3 class="font-medium text-gray-900">Analyze & Rank Matches</h3>
                            <p class="text-sm text-gray-600">AI-powered analysis to rank properties by how well they fit</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Chat Interface -->
            <div class="bg-white rounded-lg shadow-sm">
                <div class="p-4 border-b">
                    <h2 class="text-lg font-semibold text-gray-900">💬 Chat Interface</h2>
                </div>
                <div id="chat-messages" class="p-6 h-64 overflow-y-auto">
                    <div class="flex justify-start mb-4">
                        <div class="bg-blue-50 text-blue-900 px-4 py-2 rounded-lg max-w-md">
                            <p class="text-sm">Welcome! I'm your property recommendation assistant. Click "Start Finding Properties" to begin the process. I'll guide you through finding your perfect property by understanding your preferences and searching Trade Me for the best matches.</p>
                        </div>
                    </div>
                </div>
                
                <!-- Status Display -->
                <div id="status-panel" class="p-4 border-t bg-gray-50 hidden">
                    <div class="text-center">
                        <div class="inline-flex items-center space-x-2 text-blue-600">
                            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                            <span class="text-sm font-medium">Running your property recommendation system...</span>
                        </div>
                        <p class="text-xs text-gray-500 mt-1">This will take a few moments while we collect your preferences and find matching properties</p>
                    </div>
                </div>
            </div>

            <!-- Results Section -->
            <div id="results-section" class="mt-6 bg-white rounded-lg shadow-sm p-6 hidden">
                <h2 class="text-lg font-semibold text-gray-900 mb-4">🎯 Your Property Recommendations</h2>
                <div id="results-content">
                    <!-- Results will be displayed here -->
                </div>
            </div>
        </div>
    </div>

    <script>
        function addMessage(content, isUser = false) {
            const messagesContainer = document.getElementById('chat-messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`;
            
            const bgClass = isUser ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-900';
            messageDiv.innerHTML = `
                <div class="${bgClass} px-4 py-2 rounded-lg max-w-md">
                    <p class="text-sm">${content}</p>
                    <p class="text-xs opacity-70 mt-1">${new Date().toLocaleTimeString()}</p>
                </div>
            `;
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        function updateStep(stepNum, status) {
            const step = document.getElementById(`step${stepNum}`);
            const circle = step.querySelector('div div');
            
            if (status === 'running') {
                step.className = 'flex items-center space-x-3 p-3 rounded-lg bg-blue-50 border border-blue-200';
                circle.className = 'w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold animate-pulse';
            } else if (status === 'completed') {
                step.className = 'flex items-center space-x-3 p-3 rounded-lg bg-green-50 border border-green-200';
                circle.className = 'w-8 h-8 bg-green-600 rounded-full flex items-center justify-center text-white font-bold';
                circle.innerHTML = '✓';
            }
        }

        function startProcess() {
            document.getElementById('start-btn').style.display = 'none';
            document.getElementById('status-panel').classList.remove('hidden');
            
            addMessage('Great! Starting the property recommendation process for you...', false);
            addMessage('This involves three main steps that run your existing Python system:', false);
            
            // Simulate the process steps
            setTimeout(() => {
                updateStep(1, 'running');
                addMessage('🔄 Step 1: Collecting your property preferences...', false);
            }, 1000);
            
            setTimeout(() => {
                updateStep(1, 'completed');
                updateStep(2, 'running');
                addMessage('✅ Preferences collected successfully!', false);
                addMessage('🔄 Step 2: Searching Trade Me for matching properties...', false);
            }, 3000);
            
            setTimeout(() => {
                updateStep(2, 'completed');
                updateStep(3, 'running');
                addMessage('✅ Found properties on Trade Me!', false);
                addMessage('🔄 Step 3: Analyzing and ranking your best matches...', false);
            }, 5500);
            
            setTimeout(() => {
                updateStep(3, 'completed');
                document.getElementById('status-panel').classList.add('hidden');
                addMessage('✅ Analysis complete! Your personalized property recommendations are ready.', false);
                showResults();
            }, 8000);
        }

        function showResults() {
            const resultsSection = document.getElementById('results-section');
            const resultsContent = document.getElementById('results-content');
            
            resultsContent.innerHTML = `
                <div class="space-y-4">
                    <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                        <div class="flex justify-between items-start mb-2">
                            <h3 class="font-semibold text-gray-900">Sample Property Match</h3>
                            <span class="bg-green-100 text-green-800 px-2 py-1 rounded text-sm">Score: 8.5/10</span>
                        </div>
                        <p class="text-gray-600 text-sm">This is where your actual property recommendations would appear when running with real Trade Me data and your API credentials.</p>
                    </div>
                    
                    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <h4 class="font-medium text-blue-900 mb-2">🔑 To get real results:</h4>
                        <ul class="text-sm text-blue-800 space-y-1">
                            <li>• Set up your Trade Me API credentials</li>
                            <li>• Configure your OpenAI API key</li>
                            <li>• Run: <code class="bg-blue-100 px-1 rounded">python property_recommender/orchestrator.py</code></li>
                        </ul>
                    </div>
                </div>
            `;
            
            resultsSection.classList.remove('hidden');
        }
    </script>
</body>
</html>"""
            self.wfile.write(html.encode())
        else:
            super().do_GET()

if __name__ == "__main__":
    PORT = 3000
    with socketserver.TCPServer(("0.0.0.0", PORT), PropertyHandler) as httpd:
        print(f"🚀 Property Recommender Web Interface")
        print(f"🌐 Server running at http://0.0.0.0:{PORT}")
        print("📱 Open your browser to see the interface!")
        httpd.serve_forever()