/**
 * Zod schemas for runtime validation of API responses.
 * Prevents frontend crashes when backend response shapes change.
 */

import { z } from 'zod'

// ---- Session schemas ----

export const SessionSchema = z.object({
  id: z.string(),
  title: z.string().nullable().optional(),
  created_at: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional(),
  current_version: z.number().nullable().optional(),
  product_type: z.string().nullable().optional(),
  message_count: z.number().optional().default(0),
  version_count: z.number().optional().default(0),
  build_status: z.string().nullable().optional(),
  thumbnail: z.string().nullable().optional(),
})

export const SessionListSchema = z.object({
  sessions: z.array(SessionSchema),
  total: z.number().optional(),
})

// ---- Message schemas ----

export const MessageSchema = z.object({
  id: z.string(),
  role: z.enum(['user', 'assistant', 'system']).optional(),
  content: z.string().optional().default(''),
  created_at: z.string().nullable().optional(),
})

export const MessageListSchema = z.object({
  messages: z.array(MessageSchema),
})

// ---- Health check schema ----

export const HealthSchema = z.object({
  status: z.enum(['ok', 'degraded', 'error']),
  checks: z.record(z.string(), z.string()).optional(),
})
