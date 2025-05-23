import React, { useState, useEffect } from 'react';
import { MessageSquare, Home, Settings, PlayCircle, CheckCircle, AlertCircle, Clock } from 'lucide-react';

interface ProcessStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  output: string[];
  error?: string;
}

interface ProcessStatus {
  steps: ProcessStep[];
  isRunning: boolean;
}

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'system',
      content: 'Welcome! I\'m your property recommendation assistant. I\'ll help you find the perfect property by understanding your preferences and searching Trade Me for the best matches.',
      timestamp: new Date()
    }
  ]);
  
  const [processStatus, setProcessStatus] = useState<ProcessStatus | null>(null);
  const [isStarted, setIsStarted] = useState(false);
  const [results, setResults] = useState<any>(null);

  const addMessage = (role: 'user' | 'assistant' | 'system', content: string) => {
    setMessages(prev => [...prev, { role, content, timestamp: new Date() }]);
  };

  const startRecommendationProcess = async () => {
    if (isStarted) return;
    
    setIsStarted(true);
    addMessage('assistant', 'Great! Let me start the property recommendation process for you. This will happen in three main steps:');
    addMessage('assistant', '1. First, I\'ll collect your property preferences through a conversation');
    addMessage('assistant', '2. Then, I\'ll search Trade Me for properties that match your criteria');
    addMessage('assistant', '3. Finally, I\'ll analyze and rank the best matches for you');
    addMessage('assistant', 'Starting the process now...');

    try {
      const response = await fetch('/api/start-recommendation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) {
        throw new Error('Failed to start process');
      }
      
      // Start polling for status updates
      pollStatus();
    } catch (error) {
      addMessage('assistant', 'Sorry, I encountered an error starting the process. Please make sure all API credentials are properly configured.');
      setIsStarted(false);
    }
  };

  const pollStatus = async () => {
    try {
      const response = await fetch('/api/status');
      const status: ProcessStatus = await response.json();
      setProcessStatus(status);

      // Update messages based on step progress
      updateMessagesFromStatus(status);

      // Continue polling if process is running
      if (status.isRunning) {
        setTimeout(pollStatus, 2000);
      } else {
        // Process completed, try to get results
        fetchResults();
      }
    } catch (error) {
      console.error('Error polling status:', error);
      setTimeout(pollStatus, 5000); // Retry after 5 seconds
    }
  };

  const updateMessagesFromStatus = (status: ProcessStatus) => {
    status.steps.forEach(step => {
      if (step.status === 'running') {
        addMessage('system', `🔄 ${step.name}...`);
      } else if (step.status === 'completed') {
        addMessage('system', `✅ ${step.name} - Complete!`);
      } else if (step.status === 'error' && step.error) {
        addMessage('system', `❌ Error in ${step.name}: ${step.error}`);
      }
    });
  };

  const fetchResults = async () => {
    try {
      const response = await fetch('/api/results');
      if (response.ok) {
        const data = await response.json();
        setResults(data);
        addMessage('assistant', 'Perfect! I\'ve found and analyzed your property matches. Here are your personalized recommendations:');
      }
    } catch (error) {
      addMessage('assistant', 'The process completed, but I\'m having trouble loading the final results. Please check that all steps completed successfully.');
    }
  };

  const getStepIcon = (status: string) => {
    switch (status) {
      case 'running': return <Clock className="h-4 w-4 animate-spin text-blue-500" />;
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'error': return <AlertCircle className="h-4 w-4 text-red-500" />;
      default: return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <div className="w-64 bg-white shadow-lg">
        <div className="p-6 border-b">
          <div className="flex items-center space-x-2">
            <Home className="h-6 w-6 text-blue-600" />
            <h1 className="text-xl font-bold text-gray-900">Property Finder</h1>
          </div>
        </div>
        
        <div className="p-4">
          <h3 className="text-sm font-semibold text-gray-600 mb-3">Process Steps</h3>
          {processStatus?.steps.map((step, index) => (
            <div key={step.id} className="flex items-center space-x-3 p-2 rounded-lg mb-2">
              {getStepIcon(step.status)}
              <span className="text-sm text-gray-700">{step.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <div className="bg-white shadow-sm border-b p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <MessageSquare className="h-5 w-5 text-blue-600" />
              <h2 className="text-lg font-semibold text-gray-900">Property Recommendation Chat</h2>
            </div>
            {!isStarted && (
              <button
                onClick={startRecommendationProcess}
                className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
              >
                <PlayCircle className="h-4 w-4" />
                <span>Start Finding Properties</span>
              </button>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                  message.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : message.role === 'system'
                    ? 'bg-gray-100 text-gray-700 text-sm'
                    : 'bg-white text-gray-900 shadow-sm border'
                }`}
              >
                <p className="text-sm">{message.content}</p>
                <p className="text-xs opacity-70 mt-1">
                  {message.timestamp.toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Results Display */}
        {results && (
          <div className="bg-white border-t p-6">
            <h3 className="text-lg font-semibold mb-4">Your Property Recommendations</h3>
            <div className="space-y-4">
              {Array.isArray(results) ? results.slice(0, 5).map((property: any, index: number) => (
                <div key={index} className="border rounded-lg p-4 hover:shadow-md transition-shadow">
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-semibold text-gray-900">Property #{property.property_id}</h4>
                    <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-sm">
                      Score: {property.score}/10
                    </span>
                  </div>
                  <p className="text-gray-600 text-sm mb-2">{property.rationale}</p>
                </div>
              )) : (
                <p className="text-gray-600">Results are being processed...</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}