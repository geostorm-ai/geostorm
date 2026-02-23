import { Badge } from "@/components/ui/badge"
import { SEVERITY_COLORS } from "@/lib/constants"
import { cn } from "@/lib/utils"
import type { AlertSeverity } from "@/schemas/alert"

interface AlertBadgeProps {
	severity: AlertSeverity
	className?: string
}

export function AlertBadge({ severity, className }: AlertBadgeProps) {
	return (
		<Badge
			variant="secondary"
			className={cn(SEVERITY_COLORS[severity], className)}
		>
			{severity}
		</Badge>
	)
}
