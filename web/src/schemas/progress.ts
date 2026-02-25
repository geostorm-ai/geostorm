import { z } from "zod"

export const RunPhase = z.enum([
	"preparing",
	"querying",
	"analyzing",
	"complete",
	"failed",
])

export type RunPhase = z.infer<typeof RunPhase>

export const RunProgressEventSchema = z.object({
	run_id: z.string(),
	phase: RunPhase,
	completed: z.number(),
	failed: z.number(),
	total: z.number(),
	current_term: z.string().nullable(),
	current_provider: z.string().nullable(),
	status: z.string(),
})

export type RunProgressEvent = z.infer<typeof RunProgressEventSchema>
