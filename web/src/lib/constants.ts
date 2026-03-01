import type { AlertType } from "@/schemas/alert"

export const ALERT_TYPE_LABELS: Record<AlertType, string> = {
	competitor_emergence: "Competitor Emergence",
	configuration_error: "Setup Required",
	disappearance: "Disappearance",
	recommendation_share_drop: "Share Drop",
	position_degradation: "Position Drop",
	model_divergence: "Model Divergence",
	citation_domain_shift: "Citation Shift",
}

export const SEVERITY_COLORS = {
	critical: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
	warning: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
	info: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
} as const

export const DAY_NAMES = [
	"Monday",
	"Tuesday",
	"Wednesday",
	"Thursday",
	"Friday",
	"Saturday",
	"Sunday",
] as const

export const RUN_STATUS_COLORS = {
	pending: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
	running: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
	completed:
		"bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
	partial:
		"bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
	failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
	cancelled: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
} as const
