import { z } from 'zod'

// Message schema for chat
export const messageSchema = z.object({
  id: z.string(),
  role: z.enum(['user', 'assistant']),
  content: z.string(),
  timestamp: z.number(),
})

export type Message = z.infer<typeof messageSchema>

// Session schema
export const sessionSchema = z.object({
  id: z.string(),
  status: z.enum(['active', 'processing', 'complete']),
  messages: z.array(messageSchema),
  results: z.array(z.any()).optional(),
})

export type Session = z.infer<typeof sessionSchema>

// Property match schema (based on your existing structure)
export const propertyMatchSchema = z.object({
  property_id: z.number(),
  score: z.number(),
  rationale: z.string(),
})

export type PropertyMatch = z.infer<typeof propertyMatchSchema>