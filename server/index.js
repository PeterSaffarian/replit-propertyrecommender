const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5000;

app.use(express.json());
app.use(express.static('client'));

// Store chat sessions
const chatSessions = new Map();

// API route to start a new chat session
app.post('/api/start-session', (req, res) => {
  const sessionId = Date.now().toString();
  chatSessions.set(sessionId, {
    status: 'active',
    messages: [],
    step: 'profile_collection'
  });
  
  res.json({ 
    sessionId, 
    message: "Hi! I'm here to help you find the perfect property. Let's start by understanding your preferences. What type of property are you looking for, and what's your budget?" 
  });
});

// API route to send message in chat
app.post('/api/chat/:sessionId', async (req, res) => {
  const { sessionId } = req.params;
  const { message } = req.body;
  
  const session = chatSessions.get(sessionId);
  if (!session) {
    return res.status(404).json({ error: 'Session not found' });
  }

  session.messages.push({ role: 'user', content: message });

  try {
    session.messages.push({ 
      role: 'assistant', 
      content: "Perfect! I have enough information to start searching. Let me run the property recommendation pipeline to find the best matches for you. This will take a moment..." 
    });

    // Start the pipeline
    setTimeout(async () => {
      await runPropertyPipeline(sessionId);
    }, 2000);
    
    res.json({ 
      message: "Excellent! I'm now analyzing properties that match your criteria. This will take a moment...",
      status: 'processing'
    });
  } catch (error) {
    console.error('Error processing message:', error);
    res.status(500).json({ error: 'Failed to process message' });
  }
});

// API route to get session status and results
app.get('/api/session/:sessionId', (req, res) => {
  const { sessionId } = req.params;
  const session = chatSessions.get(sessionId);
  
  if (!session) {
    return res.status(404).json({ error: 'Session not found' });
  }

  // Check if results are ready
  if (fs.existsSync('./property_matches.json')) {
    try {
      const matches = JSON.parse(fs.readFileSync('./property_matches.json', 'utf8'));
      session.step = 'complete';
      session.results = matches;
      
      res.json({
        status: 'complete',
        results: matches,
        message: `Great news! I found ${matches.length} properties that match your criteria. Here are the results ranked by how well they fit your needs:`
      });
    } catch (error) {
      res.json({ status: session.step || 'processing' });
    }
  } else {
    res.json({ status: session.step || 'processing' });
  }
});

async function runPropertyPipeline(sessionId) {
  return new Promise((resolve, reject) => {
    console.log('Starting property recommendation pipeline...');
    
    // Since user_profile.json already exists, skip interactive phase and run data gathering + matching
    console.log('Using existing user profile, running data gathering and matching phases...');
    
    const pythonProcess = spawn('python', ['-m', 'property_recommender.data_gathering.orchestrator'], {
      cwd: process.cwd(),
      stdio: ['pipe', 'pipe', 'pipe']
    });

    pythonProcess.stdout.on('data', (data) => {
      console.log('Pipeline output:', data.toString());
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error('Pipeline error:', data.toString());
    });

    pythonProcess.on('close', (code) => {
      console.log(`Data gathering exited with code ${code}`);
      if (code === 0) {
        // Now run the match reasoning phase
        console.log('Running match reasoning phase...');
        const matchProcess = spawn('python', ['-m', 'property_recommender.match_reasoning.orchestrator'], {
          cwd: process.cwd(),
          stdio: ['pipe', 'pipe', 'pipe']
        });

        matchProcess.stdout.on('data', (data) => {
          console.log('Match output:', data.toString());
        });

        matchProcess.stderr.on('data', (data) => {
          console.error('Match error:', data.toString());
        });

        matchProcess.on('close', (matchCode) => {
          console.log(`Match reasoning exited with code ${matchCode}`);
          if (matchCode === 0) {
            console.log('Pipeline completed successfully');
            resolve();
          } else {
            console.error(`Match reasoning failed with code ${matchCode}`);
            reject(new Error(`Match reasoning failed with code ${matchCode}`));
          }
        });

        matchProcess.on('error', (error) => {
          console.error('Failed to start match reasoning:', error);
          reject(error);
        });
      } else {
        console.error(`Data gathering failed with code ${code}`);
        reject(new Error(`Data gathering failed with code ${code}`));
      }
    });

    pythonProcess.on('error', (error) => {
      console.error('Failed to start data gathering:', error);
      reject(error);
    });
  });
}

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
});