const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

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
app.use(express.static(path.join(__dirname, '../client')));

// Store active Python processes by session
const activeSessions = new Map();

// Serve the HTML file for all routes
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, '../client/index.html'));
});

// WebSocket connection handling
io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);

  socket.on('start_session', (sessionId) => {
    console.log('Starting session:', sessionId);
    
    // Start the Python property recommendation pipeline with limited pages for faster testing
    const pythonProcess = spawn('python', ['-m', 'property_recommender.orchestrator', '--max-pages', '1'], {
      cwd: process.cwd(),
      stdio: ['pipe', 'pipe', 'pipe']
    });

    activeSessions.set(sessionId, {
      process: pythonProcess,
      socketId: socket.id,
      phase: 'profile'
    });

    // Handle Python process output (Pete's messages)
    pythonProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log('Python output:', output);
      
      // Send Pete's messages to the client
      socket.emit('pete_message', {
        content: output.trim(),
        timestamp: Date.now()
      });
    });

    // Handle Python process errors
    pythonProcess.stderr.on('data', (data) => {
      const error = data.toString();
      console.log('Python error:', error);
      
      socket.emit('pipeline_error', {
        message: `Error: ${error.trim()}`,
        timestamp: Date.now()
      });
    });

    // Handle process completion
    pythonProcess.on('close', (code) => {
      console.log(`Python process exited with code ${code}`);
      
      if (code === 0) {
        // Try to read the results file
        try {
          const resultsPath = path.join(process.cwd(), 'property_matches.json');
          if (fs.existsSync(resultsPath)) {
            const results = JSON.parse(fs.readFileSync(resultsPath, 'utf8'));
            socket.emit('results_ready', {
              results: results,
              timestamp: Date.now()
            });
          }
        } catch (error) {
          console.log('Error reading results:', error);
        }
        
        socket.emit('pipeline_complete', {
          message: 'Property recommendation pipeline completed successfully!',
          timestamp: Date.now()
        });
      }
      
      activeSessions.delete(sessionId);
    });

    // Send initial message
    socket.emit('pete_message', {
      content: "Hello! I'm Pete, your property recommendation assistant. Let me start by gathering some information about your preferences...",
      timestamp: Date.now()
    });
  });

  socket.on('user_response', (data) => {
    const { sessionId, message } = data;
    console.log('User response:', message);
    
    const session = activeSessions.get(sessionId);
    if (session && session.process) {
      // Send user input to Python process
      session.process.stdin.write(message + '\n');
    }
  });

  socket.on('disconnect', () => {
    console.log('Client disconnected:', socket.id);
    
    // Clean up any active sessions for this socket
    for (const [sessionId, session] of activeSessions.entries()) {
      if (session.socketId === socket.id) {
        if (session.process) {
          session.process.kill();
        }
        activeSessions.delete(sessionId);
      }
    }
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
});