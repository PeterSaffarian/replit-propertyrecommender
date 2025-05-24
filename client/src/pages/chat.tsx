import { useState, useEffect, useRef } from 'react';
import { io, Socket } from 'socket.io-client';

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  results?: PropertyMatch[]
}

interface PropertyMatch {
  property_id: number
  score: number
  rationale: string
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [sessionId] = useState(() => Math.random().toString(36).substring(7));
  const socketRef = useRef<Socket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Connect to WebSocket
    const socket = io();
    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('Connected to server');
      setIsConnected(true);
      
      // Start the chat session automatically
      socket.emit('start_chat', sessionId);
    });

    socket.on('disconnect', () => {
      console.log('Disconnected from server');
      setIsConnected(false);
    });

    socket.on('assistant_message', (data) => {
      console.log('Received assistant message:', data);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.content,
        timestamp: data.timestamp
      }]);
    });

    socket.on('results_ready', (data) => {
      console.log('Received results:', data);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Great! I found ${data.results.length} properties that match your criteria. Here are the top recommendations:`,
        timestamp: data.timestamp,
        results: data.results
      }]);
    });

    socket.on('pipeline_error', (data) => {
      console.log('Pipeline error:', data);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.message,
        timestamp: data.timestamp
      }]);
    });

    return () => {
      socket.disconnect();
    };
  }, [sessionId]);

  const sendMessage = () => {
    if (!input.trim() || !socketRef.current) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: Date.now()
    };

    setMessages(prev => [...prev, userMessage]);
    
    // Send message to server via WebSocket
    socketRef.current.emit('user_message', {
      sessionId,
      message: input
    });

    setInput('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
            <span className="text-white text-sm font-bold">🏠</span>
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Property Recommendation Assistant</h1>
            <p className="text-sm text-gray-600">Find your perfect property with AI-powered recommendations</p>
          </div>
          <div className="ml-auto">
            <div className={`px-3 py-1 rounded-full text-xs font-medium ${
              isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
            }`}>
              {isConnected ? '● Connected' : '● Disconnected'}
            </div>
          </div>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="max-w-4xl mx-auto space-y-4">
          {/* Welcome message */}
          {messages.length === 0 && (
            <div className="bg-white rounded-lg p-6 border">
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-white text-sm">🤖</span>
                </div>
                <div className="flex-1">
                  <p className="text-gray-900 font-medium mb-2">Chat with your Property Assistant</p>
                  <p className="text-gray-600 mb-4">
                    Welcome! I'll help you find the perfect property. Please tell me about your preferences...
                  </p>
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <p className="text-blue-800 text-sm">
                      <strong>Pete is starting up...</strong> The conversation will begin automatically once connected.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Chat messages */}
          {messages.map((message, index) => (
            <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-3xl ${message.role === 'user' ? 'bg-blue-600 text-white' : 'bg-white border'} rounded-lg p-4`}>
                {message.role === 'assistant' && (
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-6 h-6 bg-blue-600 rounded-full flex items-center justify-center">
                      <span className="text-white text-xs">🤖</span>
                    </div>
                    <span className="font-medium text-gray-900">Pete</span>
                  </div>
                )}
                
                <p className={`${message.role === 'user' ? 'text-white' : 'text-gray-900'} whitespace-pre-wrap`}>
                  {message.content}
                </p>

                {/* Property Results */}
                {message.results && message.results.length > 0 && (
                  <div className="mt-4 space-y-3">
                    {message.results.map((match: PropertyMatch, matchIndex) => (
                      <div key={matchIndex} className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <div className="flex items-start justify-between mb-2">
                          <h4 className="font-medium text-gray-900">Property #{match.property_id}</h4>
                          <div className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm font-medium">
                            {Math.round(match.score * 100)}% match
                          </div>
                        </div>
                        <p className="text-gray-700 text-sm">{match.rationale}</p>
                      </div>
                    ))}
                  </div>
                )}

                <div className={`text-xs mt-2 ${message.role === 'user' ? 'text-blue-100' : 'text-gray-500'}`}>
                  {new Date(message.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="bg-white border-t px-6 py-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Tell me about your property preferences..."
              className="flex-1 border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={!isConnected}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || !isConnected}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          </div>
          {!isConnected && (
            <p className="text-red-600 text-sm mt-2">Connecting to property recommendation system...</p>
          )}
        </div>
      </div>
    </div>
  );
}