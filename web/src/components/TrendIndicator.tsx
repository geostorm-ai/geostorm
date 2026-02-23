import { cn } from "@/lib/utils"
import type { TrendDirection } from "@/schemas/perception"

interface TrendIndicatorProps {
	direction: TrendDirection
	className?: string
}

const config = {
	up: {
		label: "Up",
		arrow: "\u2191",
		color: "text-green-600 dark:text-green-400",
	},
	down: {
		label: "Down",
		arrow: "\u2193",
		color: "text-red-600 dark:text-red-400",
	},
	stable: { label: "Stable", arrow: "\u2192", color: "text-muted-foreground" },
} as const

export function TrendIndicator({ direction, className }: TrendIndicatorProps) {
	const { label, arrow, color } = config[direction]
	return (
		<span
			className={cn(
				"inline-flex items-center gap-1 text-sm font-medium",
				color,
				className,
			)}
		>
			<span>{arrow}</span>
			<span>{label}</span>
		</span>
	)
}
