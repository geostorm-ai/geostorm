import { cn } from "@/lib/utils"
import type { TrendDirection } from "@/schemas/perception"
import { TrendIndicator } from "./TrendIndicator"

interface ScoreDisplayProps {
	label: string
	value: number | null
	format?: "percent" | "number" | "score"
	trend?: TrendDirection
	className?: string
}

function formatValue(value: number | null, format: string): string {
	if (value === null) return "--"
	switch (format) {
		case "percent":
			return `${Math.round(value * 100)}%`
		case "score":
			return value.toFixed(1)
		default:
			return String(Math.round(value))
	}
}

export function ScoreDisplay({
	label,
	value,
	format = "score",
	trend,
	className,
}: ScoreDisplayProps) {
	return (
		<div className={cn("flex flex-col gap-1", className)}>
			<span className="text-sm text-muted-foreground">{label}</span>
			<div className="flex items-baseline gap-2">
				<span className="text-3xl font-bold tracking-tight">
					{formatValue(value, format)}
				</span>
				{trend && <TrendIndicator direction={trend} />}
			</div>
		</div>
	)
}
