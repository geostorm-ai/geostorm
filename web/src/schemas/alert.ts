import { z } from "zod"

export const AlertType = z.enum([
	"competitor_emergence",
	"disappearance",
	"recommendation_share_drop",
	"position_degradation",
	"model_divergence",
	"citation_domain_shift",
])

export type AlertType = z.infer<typeof AlertType>

export const AlertSeverity = z.enum(["info", "warning", "critical"])

export type AlertSeverity = z.infer<typeof AlertSeverity>

export const AlertSchema = z.object({
	id: z.string(),
	project_id: z.string(),
	alert_type: AlertType,
	severity: AlertSeverity,
	title: z.string(),
	message: z.string(),
	explanation: z.string().nullable(),
	is_acknowledged: z.boolean(),
	acknowledged_at: z.string().nullable(),
	acknowledged_by: z.string().nullable(),
	created_at: z.string(),
})

export type Alert = z.infer<typeof AlertSchema>

export const AlertConfigSchema = z.object({
	id: z.string(),
	project_id: z.string(),
	channel: z.enum(["email", "slack", "webhook", "in_app"]),
	endpoint: z.string(),
	alert_types: z.array(AlertType),
	min_severity: AlertSeverity,
	is_enabled: z.boolean(),
	created_at: z.string(),
	updated_at: z.string(),
})

export type AlertConfig = z.infer<typeof AlertConfigSchema>
