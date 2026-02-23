import { z } from "zod"

export const TrendDirection = z.enum(["up", "down", "stable"])

export type TrendDirection = z.infer<typeof TrendDirection>

export const PerceptionDataPointSchema = z.object({
	date: z.string(),
	overall_score: z.number().nullable(),
	recommendation_share: z.number().nullable(),
	position_avg: z.number().nullable(),
	competitor_delta: z.number().nullable(),
	trend_direction: TrendDirection,
})

export type PerceptionDataPoint = z.infer<typeof PerceptionDataPointSchema>

export const PerceptionResponseSchema = z.object({
	project_id: z.string(),
	data: z.array(PerceptionDataPointSchema),
})

export type PerceptionResponse = z.infer<typeof PerceptionResponseSchema>
