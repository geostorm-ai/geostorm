import { z } from "zod"

export const BrandSchema = z.object({
	id: z.string(),
	project_id: z.string(),
	name: z.string(),
	aliases: z.array(z.string()),
	description: z.string().nullable(),
	website: z.string().nullable(),
	created_at: z.string(),
	updated_at: z.string(),
})

export type Brand = z.infer<typeof BrandSchema>

export const CompetitorSchema = z.object({
	id: z.string(),
	project_id: z.string(),
	name: z.string(),
	aliases: z.array(z.string()),
	website: z.string().nullable(),
	is_active: z.boolean(),
	created_at: z.string(),
	updated_at: z.string(),
})

export type Competitor = z.infer<typeof CompetitorSchema>

export const TermSchema = z.object({
	id: z.string(),
	project_id: z.string(),
	name: z.string(),
	description: z.string().nullable(),
	is_active: z.boolean(),
	created_at: z.string(),
	updated_at: z.string(),
})

export type Term = z.infer<typeof TermSchema>

export const ScheduleSchema = z.object({
	id: z.string(),
	project_id: z.string(),
	hour_of_day: z.number(),
	days_of_week: z.array(z.number()),
	is_active: z.boolean(),
	last_run_at: z.string().nullable(),
	next_run_at: z.string().nullable(),
	created_at: z.string(),
	updated_at: z.string(),
})

export type Schedule = z.infer<typeof ScheduleSchema>

export const ProjectSchema = z.object({
	id: z.string(),
	name: z.string(),
	description: z.string().nullable(),
	is_demo: z.boolean(),
	created_at: z.string(),
	updated_at: z.string(),
	latest_score: z.number().nullable().optional(),
	run_count: z.number().optional(),
	active_alert_count: z.number().optional(),
})

export type Project = z.infer<typeof ProjectSchema>

export const ProjectDetailSchema = ProjectSchema.extend({
	brand: BrandSchema.nullable(),
	competitors: z.array(CompetitorSchema),
	terms: z.array(TermSchema),
	schedule: ScheduleSchema.nullable(),
})

export type ProjectDetail = z.infer<typeof ProjectDetailSchema>

export const CreateProjectRequestSchema = z.object({
	name: z.string().min(1).max(255),
	description: z.string().nullable().optional(),
	brand_name: z.string().min(1).max(255),
	brand_aliases: z.array(z.string()).optional(),
	brand_description: z.string().nullable().optional(),
	brand_website: z.string().nullable().optional(),
})

export type CreateProjectRequest = z.infer<typeof CreateProjectRequestSchema>
