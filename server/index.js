const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const http = require('http');
const socketIo = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

const PORT = process.env.PORT || 5000;

app.use(express.json());
app.use(express.static('client'));

// In-memory storage for active Python processes
const activePipelines = new Map();

// Socket.IO connection handling
io.on('connection', (socket) => {
  console.log('User connected:', socket.id);

  socket.on('start_chat', (sessionId) => {
    console.log('Starting chat session:', sessionId);
    
    // Start the Python pipeline for this session
    startPythonPipeline(sessionId, socket);
  });

  socket.on('user_message', (data) => {
    const { sessionId, message } = data;
    console.log('User message received:', message);
    
    // Send the user's message to the Python pipeline
    const pipeline = activePipelines.get(sessionId);
    if (pipeline && pipeline.process) {
      pipeline.process.stdin.write(message + '\n');
    }
  });

  socket.on('disconnect', () => {
    console.log('User disconnected:', socket.id);
  });
});

function startPythonPipeline(sessionId, socket) {
  console.log('Starting Python pipeline for session:', sessionId);
  
  const pythonProcess = spawn('python', ['-m', 'property_recommender.orchestrator'], {
    cwd: process.cwd(),
    stdio: ['pipe', 'pipe', 'pipe']
  });

  // Store the process for this session
  activePipelines.set(sessionId, {
    process: pythonProcess,
    socket: socket
  });

  pythonProcess.stdout.on('data', (data) => {
    const output = data.toString();
    console.log('Pipeline output:', output);
    
    // Parse the output and send to the frontend
    if (output.includes('Assistant:') || output.includes('A:')) {
      // Extract the assistant message
      const assistantMessage = output.split('Assistant:')[1] || output.split('A:')[1];
      if (assistantMessage) {
        socket.emit('assistant_message', {
          content: assistantMessage.trim(),
          timestamp: Date.now()
        });
      }
    }
    
    // Check if pipeline completed successfully
    if (output.includes('Pipeline completed') || output.includes('property_matches.json')) {
      // Try to load and send results
      const resultsPath = path.join(process.cwd(), 'property_matches.json');
      if (fs.existsSync(resultsPath)) {
        const results = JSON.parse(fs.readFileSync(resultsPath, 'utf8'));
        socket.emit('results_ready', {
          results: results.slice(0, 5), // Top 5 matches
          timestamp: Date.now()
        });
      }
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error('Pipeline error:', data.toString());
  });

  pythonProcess.on('close', (code) => {
    console.log(`Pipeline process exited with code ${code}`);
    activePipelines.delete(sessionId);
    
    if (code === 0) {
      // Try to load results one more time
      const resultsPath = path.join(process.cwd(), 'property_matches.json');
      if (fs.existsSync(resultsPath)) {
        const results = JSON.parse(fs.readFileSync(resultsPath, 'utf8'));
        socket.emit('results_ready', {
          results: results.slice(0, 5),
          timestamp: Date.now()
        });
      }
    } else {
      socket.emit('pipeline_error', {
        message: 'Pipeline encountered an error. Please try again.',
        timestamp: Date.now()
      });
    }
  });

  pythonProcess.on('error', (error) => {
    console.error('Failed to start pipeline:', error);
    socket.emit('pipeline_error', {
      message: 'Failed to start the recommendation engine.',
      timestamp: Date.now()
    });
  });
}

// Fallback REST endpoints for compatibility
app.get('/api/sessions/:sessionId/messages', (req, res) => {
  res.json([]);
});

app.post('/api/sessions/:sessionId/messages', (req, res) => {
  res.json({ message: 'Use WebSocket connection for real-time chat' });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
});