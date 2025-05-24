import express from 'express';
import cors from 'cors';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

const app = express();
const PORT = parseInt(process.env.PORT || '3001');

app.use(cors());
app.use(express.json());

// Store chat sessions
const chatSessions = new Map();

// API route to start a new chat session
app.post('/api/start-session', (req: express.Request, res: express.Response) => {
  const sessionId = Date.now().toString();
  chatSessions.set(sessionId, {
    status: 'active',
    messages: [],
    step: 'profile_collection'
  });
  
  res.json({ sessionId, message: "Hi! I'm here to help you find the perfect property. Let's start by understanding your preferences. What type of property are you looking for?" });
});

// API route to send message in chat
app.post('/api/chat/:sessionId', async (req: express.Request, res: express.Response) => {
  const { sessionId } = req.params;
  const { message } = req.body;
  
  const session = chatSessions.get(sessionId);
  if (!session) {
    return res.status(404).json({ error: 'Session not found' });
  }

  // Add user message to session
  session.messages.push({ role: 'user', content: message });

  try {
    // Simulate collecting enough information, then trigger the pipeline
    session.messages.push({ 
      role: 'assistant', 
      content: "Thank you for that information! Let me gather a few more details and then I'll search for properties that match your needs. This may take a few moments..." 
    });

    // Start the property recommendation pipeline
    setTimeout(async () => {
      await runPropertyPipeline(sessionId);
    }, 2000);
    
    res.json({ 
      message: "Perfect! I'm now processing your preferences and searching for the best properties. This will take a moment...",
      status: 'processing'
    });
  } catch (error) {
    console.error('Error processing message:', error);
    res.status(500).json({ error: 'Failed to process message' });
  }
});

// API route to get session status and results
app.get('/api/session/:sessionId', (req: express.Request, res: express.Response) => {
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
        message: `Excellent! I found ${matches.length} properties that match your criteria. Here are the results ranked by how well they fit your needs:`
      });
    } catch (error) {
      res.json({ status: session.step || 'processing' });
    }
  } else {
    res.json({ status: session.step || 'processing' });
  }
});

async function runPropertyPipeline(sessionId: string): Promise<void> {
  return new Promise((resolve, reject) => {
    console.log('Starting property recommendation pipeline...');
    
    const pythonProcess = spawn('python', ['-m', 'property_recommender.orchestrator'], {
      cwd: process.cwd(),
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let output = '';
    let errorOutput = '';

    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
      console.log('Pipeline output:', data.toString());
    });

    pythonProcess.stderr.on('data', (data) => {
      errorOutput += data.toString();
      console.error('Pipeline error:', data.toString());
    });

    pythonProcess.on('close', (code) => {
      console.log(`Pipeline process exited with code ${code}`);
      if (code === 0) {
        console.log('Pipeline completed successfully');
        resolve();
      } else {
        console.error(`Pipeline failed with code ${code}`);
        console.error('Error output:', errorOutput);
        reject(new Error(`Pipeline failed with code ${code}`));
      }
    });

    pythonProcess.on('error', (error) => {
      console.error('Failed to start pipeline:', error);
      reject(error);
    });
  });
}

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
});