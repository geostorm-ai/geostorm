import { useState } from "react"
import { AlertBadge } from "@/components/AlertBadge"
import { EmptyState } from "@/components/EmptyState"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useAcknowledgeAlert, useAlerts } from "@/hooks/useAlerts"
import { ALERT_TYPE_LABELS } from "@/lib/constants"
import type { Alert, AlertSeverity } from "@/schemas/alert"

interface AlertsFeedProps {
	projectId: string
	runCount?: number
}

const SEVERITY_ORDER: Record<AlertSeverity, number> = {
	critical: 0,
	warning: 1,
	info: 2,
}

function formatRelativeTime(dateStr: string): string {
	const now = Date.now()
	const date = new Date(dateStr).getTime()
	const diffMs = now - date
	const diffMin = Math.floor(diffMs / 60_000)
	const diffHr = Math.floor(diffMs / 3_600_000)
	const diffDay = Math.floor(diffMs / 86_400_000)

	if (diffMin < 1) return "just now"
	if (diffMin < 60) return `${diffMin}m ago`
	if (diffHr < 24) return `${diffHr}h ago`
	return `${diffDay}d ago`
}

function AlertItem({
	alert,
	onAcknowledge,
	isAcknowledging,
}: {
	alert: Alert
	onAcknowledge: (id: string) => void
	isAcknowledging: boolean
}) {
	return (
		<div className="flex items-start gap-4 border-b py-4 last:border-b-0">
			<div className="flex-1 space-y-1">
				<div className="flex items-center gap-2">
					<AlertBadge severity={alert.severity} />
					<span className="text-xs text-muted-foreground">
						{ALERT_TYPE_LABELS[alert.alert_type]}
					</span>
				</div>
				<p className="text-sm font-medium">{alert.title}</p>
				<p className="text-sm text-muted-foreground">{alert.message}</p>
				<p className="text-xs text-muted-foreground">
					{formatRelativeTime(alert.created_at)}
				</p>
			</div>
			<Button
				variant="outline"
				size="sm"
				onClick={() => onAcknowledge(alert.id)}
				disabled={isAcknowledging}
			>
				{isAcknowledging ? "..." : "Acknowledge"}
			</Button>
		</div>
	)
}

function LoadingSkeleton() {
	return (
		<div className="space-y-4">
			{[1, 2, 3].map((i) => (
				<div key={i} className="flex items-start gap-4 border-b py-4">
					<div className="flex-1 space-y-2">
						<Skeleton className="h-5 w-24" />
						<Skeleton className="h-4 w-3/4" />
						<Skeleton className="h-4 w-1/2" />
					</div>
					<Skeleton className="h-8 w-24" />
				</div>
			))}
		</div>
	)
}

export function AlertsFeed({ projectId, runCount }: AlertsFeedProps) {
	const { data, isLoading, error } = useAlerts(projectId, {
		acknowledged: false,
	})
	const acknowledgeMutation = useAcknowledgeAlert()
	const [acknowledgingIds, setAcknowledgingIds] = useState<Set<string>>(
		new Set(),
	)

	const alerts = data?.items ?? []
	const sorted = [...alerts].sort((a, b) => {
		const sevDiff = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
		if (sevDiff !== 0) return sevDiff
		return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
	})

	function handleAcknowledge(id: string) {
		setAcknowledgingIds((prev) => new Set(prev).add(id))
		acknowledgeMutation.mutate(id, {
			onSettled: () => {
				setAcknowledgingIds((prev) => {
					const next = new Set(prev)
					next.delete(id)
					return next
				})
			},
		})
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle className="text-lg">Active Alerts</CardTitle>
			</CardHeader>
			<CardContent>
				{isLoading && <LoadingSkeleton />}

				{error && (
					<p className="text-sm text-destructive">
						Failed to load alerts. Please try again later.
					</p>
				)}

				{!isLoading && !error && sorted.length === 0 && (
					<EmptyState
						className="py-4"
						icon={
							<svg
								xmlns="http://www.w3.org/2000/svg"
								width="24"
								height="24"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								strokeWidth="2"
								strokeLinecap="round"
								strokeLinejoin="round"
								role="img"
								aria-label="Checkmark"
							>
								<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
								<polyline points="22 4 12 14.01 9 11.01" />
							</svg>
						}
						title={
							runCount === undefined || runCount >= 2
								? "No active alerts"
								: runCount === 0
									? "No monitoring data yet"
									: "Establishing baseline"
						}
						description={
							runCount === undefined || runCount >= 2
								? "Perception is stable — no issues detected."
								: runCount === 0
									? "Run your first monitor to establish a baseline."
									: "Alerts will appear after the next monitoring run detects changes."
						}
					/>
				)}

				{!isLoading && !error && sorted.length > 0 && (
					<div>
						{sorted.map((alert) => (
							<AlertItem
								key={alert.id}
								alert={alert}
								onAcknowledge={handleAcknowledge}
								isAcknowledging={acknowledgingIds.has(alert.id)}
							/>
						))}
					</div>
				)}
			</CardContent>
		</Card>
	)
}
