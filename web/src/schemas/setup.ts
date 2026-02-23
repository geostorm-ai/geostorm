import { z } from "zod"

export const SetupStatusSchema = z.object({
	has_api_key: z.boolean(),
	has_projects: z.boolean(),
	project_count: z.number(),
})

export type SetupStatus = z.infer<typeof SetupStatusSchema>

export const ApiKeyStatusSchema = z.object({
	configured: z.boolean(),
	source: z.enum(["database", "environment"]).nullable(),
})

export type ApiKeyStatus = z.infer<typeof ApiKeyStatusSchema>
