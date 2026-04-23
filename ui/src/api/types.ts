import { z } from "zod";

export const StopSchema = z.object({
  time: z.string(),
  name: z.string(),
  category: z.string(),
  vibe: z.string(),
  address: z.string().default(""),
  cost: z.string().default(""),
  tips: z.string().default(""),
  degen_score: z.number().min(1).max(10).default(5),
});
export type Stop = z.infer<typeof StopSchema>;

export const ItinerarySchema = z.object({
  city: z.string(),
  date: z.string(),
  vibe: z.string(),
  group_size: z.number(),
  stops: z.array(StopSchema).default([]),
  total_estimated_cost: z.string().default(""),
  survival_tips: z.string().default(""),
});
export type Itinerary = z.infer<typeof ItinerarySchema>;

export const NightOutInputSchema = z.object({
  city: z.string(),
  vibe: z.string(),
  date: z.string(),
  group_size: z.number().default(4),
  notes: z.string().default(""),
});
export type NightOutInput = z.infer<typeof NightOutInputSchema>;

export const RunRecordSchema = z.object({
  run_id: z.string(),
  status: z.enum(["pending", "running", "completed", "failed"]),
  created_at: z.string(),
  completed_at: z.string().nullable().optional(),
  input: NightOutInputSchema,
  error: z.string().nullable().optional(),
});
export type RunRecord = z.infer<typeof RunRecordSchema>;

export const RunResponseSchema = z.object({
  record: RunRecordSchema,
  itinerary: ItinerarySchema.nullable().optional(),
});
export type RunResponse = z.infer<typeof RunResponseSchema>;
