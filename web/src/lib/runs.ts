import { RUN_STATUS_COLORS } from "@/lib/constants"
import type { Run } from "@/schemas/run"

export function getRunDisplay(run: Run) {
	const isPartial = run.status === "completed" && run.failed_queries > 0
	const displayStatus = isPartial ? "partial" : run.status
	const statusColor =
		RUN_STATUS_COLORS[displayStatus as keyof typeof RUN_STATUS_COLORS] ?? ""
	return { displayStatus, statusColor, isPartial }
}
