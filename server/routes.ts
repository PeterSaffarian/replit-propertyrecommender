import express from 'express'
import { spawn } from 'child_process'
import fs from 'fs'

const router = express.Router()

// Store chat sessions
const chatSessions = new Map()

// Start a new chat session
router.post('/start-session', (req, res) => {
  const sessionId = Date.now().toString()
  chatSessions.set(sessionId, {
    status: 'active',
    messages: [],
    step: 'profile_collection'
  })
  
  res.json({ 
    sessionId, 
    message: "Hi! I'm here to help you find the perfect property. Let's start by understanding your preferences. What type of property are you looking for, and what's your budget?" 
  })
})

// Send message in chat
router.post('/chat/:sessionId', async (req, res) => {
  const { sessionId } = req.params
  const { message } = req.body
  
  const session = chatSessions.get(sessionId)
  if (!session) {
    return res.status(404).json({ error: 'Session not found' })
  }

  session.messages.push({ role: 'user', content: message })

  try {
    session.messages.push({ 
      role: 'assistant', 
      content: "Perfect! I have enough information to start searching. Let me run the property recommendation pipeline to find the best matches for you. This will take a moment..." 
    })

    // Start the pipeline
    setTimeout(async () => {
      await runPropertyPipeline(sessionId)
    }, 2000)
    
    res.json({ 
      message: "Excellent! I'm now analyzing properties that match your criteria. This will take a moment...",
      status: 'processing'
    })
  } catch (error) {
    console.error('Error processing message:', error)
    res.status(500).json({ error: 'Failed to process message' })
  }
})

// Get session status and results
router.get('/session/:sessionId', (req, res) => {
  const { sessionId } = req.params
  const session = chatSessions.get(sessionId)
  
  if (!session) {
    return res.status(404).json({ error: 'Session not found' })
  }

  // Check if results are ready
  if (fs.existsSync('./property_matches.json')) {
    try {
      const matches = JSON.parse(fs.readFileSync('./property_matches.json', 'utf8'))
      session.step = 'complete'
      session.results = matches
      
      res.json({
        status: 'complete',
        results: matches,
        message: `Great news! I found ${matches.length} properties that match your criteria. Here are the results ranked by how well they fit your needs:`
      })
    } catch (error) {
      res.json({ status: session.step || 'processing' })
    }
  } else {
    res.json({ status: session.step || 'processing' })
  }
})

async function runPropertyPipeline(sessionId: string): Promise<void> {
  return new Promise((resolve, reject) => {
    console.log('Starting property recommendation pipeline...')
    
    const pythonProcess = spawn('python', ['-m', 'property_recommender.orchestrator'], {
      cwd: process.cwd(),
      stdio: ['pipe', 'pipe', 'pipe']
    })

    pythonProcess.stdout.on('data', (data) => {
      console.log('Pipeline output:', data.toString())
    })

    pythonProcess.stderr.on('data', (data) => {
      console.error('Pipeline error:', data.toString())
    })

    pythonProcess.on('close', (code) => {
      console.log(`Pipeline process exited with code ${code}`)
      if (code === 0) {
        console.log('Pipeline completed successfully')
        resolve()
      } else {
        console.error(`Pipeline failed with code ${code}`)
        reject(new Error(`Pipeline failed with code ${code}`))
      }
    })

    pythonProcess.on('error', (error) => {
      console.error('Failed to start pipeline:', error)
      reject(error)
    })
  })
}

export default router