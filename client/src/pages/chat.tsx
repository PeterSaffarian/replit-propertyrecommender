import { useState, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { apiRequest, queryClient } from '@/lib/queryClient'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Loader2, Send, Home, DollarSign, MapPin } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

interface PropertyMatch {
  property_id: number
  score: number
  rationale: string
}

interface SessionResponse {
  status: 'active' | 'processing' | 'complete'
  results?: PropertyMatch[]
  message?: string
}

export default function Chat() {
  const [sessionId, setSessionId] = useState<string>('')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)

  // Start a new session
  const startSessionMutation = useMutation({
    mutationFn: () => apiRequest('/start-session', { method: 'POST' }),
    onSuccess: (data) => {
      setSessionId(data.sessionId)
      setMessages([{
        role: 'assistant',
        content: data.message,
        timestamp: Date.now()
      }])
    }
  })

  // Send a message
  const sendMessageMutation = useMutation({
    mutationFn: (message: string) => 
      apiRequest(`/chat/${sessionId}`, {
        method: 'POST',
        body: JSON.stringify({ message })
      }),
    onSuccess: (data) => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.message,
        timestamp: Date.now()
      }])
      if (data.status === 'processing') {
        setIsProcessing(true)
      }
    }
  })

  // Poll for session status when processing
  const { data: sessionData } = useQuery<SessionResponse>({
    queryKey: [`/session/${sessionId}`],
    enabled: isProcessing && !!sessionId,
    refetchInterval: 3000,
  })

  // Handle session status updates
  useEffect(() => {
    if (sessionData?.status === 'complete' && sessionData.results) {
      setIsProcessing(false)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: sessionData.message || 'Results are ready!',
        timestamp: Date.now()
      }])
    }
  }, [sessionData])

  const handleSendMessage = () => {
    if (!input.trim() || !sessionId) return

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: Date.now()
    }

    setMessages(prev => [...prev, userMessage])
    sendMessageMutation.mutate(input)
    setInput('')
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // Start session on component mount
  useEffect(() => {
    if (!sessionId) {
      startSessionMutation.mutate()
    }
  }, [])

  const formatScore = (score: number) => {
    return `${Math.round(score * 100)}%`
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'bg-green-500'
    if (score >= 0.6) return 'bg-yellow-500'
    return 'bg-orange-500'
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="container mx-auto max-w-4xl p-4">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Property Recommendation Assistant
          </h1>
          <p className="text-gray-600 dark:text-gray-300">
            Find your perfect property with AI-powered recommendations
          </p>
        </div>

        <div className="grid gap-6">
          {/* Chat Section */}
          <Card className="h-96">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                Chat with your Property Assistant
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-64 p-4">
                <div className="space-y-4">
                  {messages.map((message, index) => (
                    <div
                      key={index}
                      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                          message.role === 'user'
                            ? 'bg-blue-500 text-white'
                            : 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
                        }`}
                      >
                        {message.content}
                      </div>
                    </div>
                  ))}
                  {(sendMessageMutation.isPending || isProcessing) && (
                    <div className="flex justify-start">
                      <div className="bg-gray-200 dark:bg-gray-700 px-4 py-2 rounded-lg">
                        <Loader2 className="w-4 h-4 animate-spin" />
                      </div>
                    </div>
                  )}
                </div>
              </ScrollArea>
              
              <div className="p-4 border-t">
                <div className="flex gap-2">
                  <Input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Tell me about your property preferences..."
                    disabled={sendMessageMutation.isPending || isProcessing}
                  />
                  <Button
                    onClick={handleSendMessage}
                    disabled={!input.trim() || sendMessageMutation.isPending || isProcessing}
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Results Section */}
          {sessionData?.results && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Home className="w-5 h-5" />
                  Property Recommendations
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {sessionData.results.map((match: PropertyMatch, index) => (
                    <div
                      key={match.property_id}
                      className="border rounded-lg p-4 hover:shadow-md transition-shadow"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <Badge variant="secondary" className="text-sm">
                            #{index + 1}
                          </Badge>
                          <span className="font-semibold text-lg">
                            Property ID: {match.property_id}
                          </span>
                        </div>
                        <Badge className={`${getScoreColor(match.score)} text-white`}>
                          {formatScore(match.score)} Match
                        </Badge>
                      </div>
                      
                      <p className="text-gray-600 dark:text-gray-300 leading-relaxed">
                        {match.rationale}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}