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
// Serve static files from client/dist if it exists, otherwise serve from client
const path = require('path');
const fs = require('fs');

if (fs.existsSync(path.join(__dirname, '../client/dist'))) {
  app.use(express.static(path.join(__dirname, '../client/dist')));
} else {
  app.use(express.static(path.join(__dirname, '../client')));
}

// Serve React app for any non-API routes
app.get('*', (req, res) => {
  if (req.path.startsWith('/api')) return;
  
  if (fs.existsSync(path.join(__dirname, '../client/dist/index.html'))) {
    res.sendFile(path.join(__dirname, '../client/dist/index.html'));
  } else {
    res.sendFile(path.join(__dirname, '../client/index.html'));
  }
});

// Store active Python processes by session
const activeSessions = new Map();

io.on('connection', (socket) => {
  console.log('User connected:', socket.id);

  socket.on('start_session', (sessionId) => {
    console.log('Starting new session:', sessionId);
    
    // Start Python orchestrator
    const pythonProcess = spawn('python', ['-m', 'property_recommender.orchestrator'], {
      cwd: process.cwd(),
      stdio: ['pipe', 'pipe', 'pipe']
    });

    // Store the session
    activeSessions.set(sessionId, {
      process: pythonProcess,
      socket: socket,
      buffer: ''
    });

    // Handle Python output
    pythonProcess.stdout.on('data', (data) => {
      const session = activeSessions.get(sessionId);
      if (!session) return;

      const output = data.toString();
      session.buffer += output;
      
      console.log('Raw Python output:', output);

      // Look for Pete's messages - they start with "Assistant: "
      const lines = session.buffer.split('\n');
      
      for (let i = 0; i < lines.length - 1; i++) {
        const line = lines[i];
        
        // Pete's message detection
        if (line.startsWith('Assistant: ')) {
          const peteMessage = line.substring(11); // Remove "Assistant: "
          console.log('Pete says:', peteMessage);
          
          socket.emit('pete_message', {
            content: peteMessage,
            timestamp: Date.now()
          });
        }
        
        // Phase detection
        if (line.includes('Phase 1:')) {
          socket.emit('phase_update', { phase: 'profile', message: line });
        } else if (line.includes('Phase 2:')) {
          socket.emit('phase_update', { phase: 'data', message: line });
        } else if (line.includes('Phase 3:')) {
          socket.emit('phase_update', { phase: 'matching', message: line });
        } else if (line.includes('Pipeline complete')) {
          // Load and send final results
          const resultsPath = path.join(process.cwd(), 'property_matches.json');
          if (fs.existsSync(resultsPath)) {
            const results = JSON.parse(fs.readFileSync(resultsPath, 'utf8'));
            socket.emit('results_ready', {
              results: results.slice(0, 5),
              timestamp: Date.now()
            });
          }
        }
      }
      
      // Keep the last incomplete line
      session.buffer = lines[lines.length - 1];
    });

    pythonProcess.stderr.on('data', (data) => {
      console.log('Python stderr:', data.toString());
    });

    pythonProcess.on('close', (code) => {
      console.log(`Python process exited with code ${code}`);
      activeSessions.delete(sessionId);
      
      if (code === 0) {
        socket.emit('pipeline_complete', { success: true });
      } else {
        socket.emit('pipeline_error', { message: 'Pipeline failed' });
      }
    });

    pythonProcess.on('error', (error) => {
      console.error('Failed to start Python process:', error);
      socket.emit('pipeline_error', { message: 'Failed to start recommendation system' });
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
    console.log('User disconnected:', socket.id);
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
});