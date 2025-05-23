import express from 'express';
import cors from 'cors';
import { spawn } from 'child_process';
import { join } from 'path';
import { readFileSync, existsSync } from 'fs';

const app = express();
const port = parseInt(process.env.PORT || '3001', 10);

app.use(cors());
app.use(express.json());

// Serve static files from client build
app.use(express.static(join(process.cwd(), 'client')));

interface ProcessStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  output: string[];
  error?: string;
}

let currentProcess: {
  steps: ProcessStep[];
  isRunning: boolean;
} = {
  steps: [
    { id: 'profile', name: 'Collecting your preferences', status: 'pending', output: [] },
    { id: 'gathering', name: 'Finding properties on Trade Me', status: 'pending', output: [] },
    { id: 'matching', name: 'Analyzing matches for you', status: 'pending', output: [] }
  ],
  isRunning: false
};

// Start the property recommendation process
app.post('/api/start-recommendation', (req, res) => {
  if (currentProcess.isRunning) {
    return res.status(400).json({ error: 'Process already running' });
  }

  // Reset process state
  currentProcess = {
    steps: [
      { id: 'profile', name: 'Collecting your preferences', status: 'pending', output: [] },
      { id: 'gathering', name: 'Finding properties on Trade Me', status: 'pending', output: [] },
      { id: 'matching', name: 'Analyzing matches for you', status: 'pending', output: [] }
    ],
    isRunning: true
  };

  // Start the Python orchestrator
  const pythonProcess = spawn('python', ['-m', 'property_recommender.orchestrator'], {
    cwd: process.cwd(),
    stdio: ['pipe', 'pipe', 'pipe']
  });

  let currentStepIndex = 0;

  pythonProcess.stdout.on('data', (data) => {
    const output = data.toString();
    console.log('Python output:', output);
    
    if (currentStepIndex < currentProcess.steps.length) {
      currentProcess.steps[currentStepIndex].output.push(output);
      
      // Simple step detection based on output content
      if (output.includes('profile') || output.includes('user_interaction')) {
        currentProcess.steps[0].status = 'running';
      } else if (output.includes('gathering') || output.includes('Trade Me')) {
        currentProcess.steps[0].status = 'completed';
        currentProcess.steps[1].status = 'running';
        currentStepIndex = 1;
      } else if (output.includes('matching') || output.includes('reasoning')) {
        currentProcess.steps[1].status = 'completed';
        currentProcess.steps[2].status = 'running';
        currentStepIndex = 2;
      }
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    const error = data.toString();
    console.error('Python error:', error);
    if (currentStepIndex < currentProcess.steps.length) {
      currentProcess.steps[currentStepIndex].error = error;
      currentProcess.steps[currentStepIndex].status = 'error';
    }
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
    currentProcess.isRunning = false;
    if (code === 0 && currentStepIndex < currentProcess.steps.length) {
      currentProcess.steps[currentStepIndex].status = 'completed';
    }
  });

  res.json({ message: 'Process started', status: currentProcess });
});

// Get current process status
app.get('/api/status', (req, res) => {
  res.json(currentProcess);
});

// Get results if available
app.get('/api/results', (req, res) => {
  try {
    const resultsPath = join(process.cwd(), 'property_matches.json');
    if (existsSync(resultsPath)) {
      const results = JSON.parse(readFileSync(resultsPath, 'utf-8'));
      res.json(results);
    } else {
      res.status(404).json({ error: 'Results not yet available' });
    }
  } catch (error) {
    res.status(500).json({ error: 'Failed to read results' });
  }
});

// Serve React app for all other routes
app.get('*', (req, res) => {
  res.sendFile(join(process.cwd(), 'client', 'index.html'));
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Server running at http://0.0.0.0:${port}`);
});