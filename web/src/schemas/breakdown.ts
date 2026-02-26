import { z } from "zod"

export const BreakdownByTermSchema = z.object({
	term_id: z.string(),
	term_name: z.string(),
	recommendation_share: z.number(),
	position_avg: z.number().nullable(),
})

export type BreakdownByTerm = z.infer<typeof BreakdownByTermSchema>

export const BreakdownByProviderSchema = z.object({
	provider_name: z.string(),
	recommendation_share: z.number(),
	position_avg: z.number().nullable(),
})

export type BreakdownByProvider = z.infer<typeof BreakdownByProviderSchema>

export const PerceptionBreakdownResponseSchema = z.object({
	project_id: z.string(),
	total_responses: z.number(),
	brand_mentions: z.number(),
	ranked_responses: z.number(),
	by_term: z.array(BreakdownByTermSchema),
	by_provider: z.array(BreakdownByProviderSchema),
})

export type PerceptionBreakdownResponse = z.infer<typeof PerceptionBreakdownResponseSchema>
