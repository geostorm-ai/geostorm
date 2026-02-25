import { EmptyState } from "@/components/EmptyState"
import { ScoreDisplay } from "@/components/ScoreDisplay"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { usePerception } from "@/hooks/usePerception"
import { useRuns } from "@/hooks/useRuns"
import { cn } from "@/lib/utils"
import { getRunDisplay } from "@/lib/runs"
import { BarChart3 } from "lucide-react"
import type { Run } from "@/schemas/run"

interface SignalPanelProps {
	projectId: string
}

function RunItem({ run }: { run: Run }) {
	const { displayStatus, statusColor, isPartial } = getRunDisplay(run)

	return (
		<div className="flex items-center justify-between border-b py-3 last:border-b-0">
			<div className="flex items-center gap-3">
				<Badge variant="secondary" className={cn(statusColor)}>
					{displayStatus}
				</Badge>
				<span className="text-sm text-muted-foreground">
					{new Date(run.created_at).toLocaleDateString()}
				</span>
			</div>
			<span className="text-xs text-muted-foreground">
				{run.completed_queries}/{run.total_queries} queries
				{isPartial && (
					<span className="ml-1 text-amber-600 dark:text-amber-400">
						({run.failed_queries} failed)
					</span>
				)}
			</span>
		</div>
	)
}

function LoadingSkeleton() {
	return (
		<div className="space-y-6">
			<div className="flex flex-col gap-2">
				<Skeleton className="h-4 w-24" />
				<Skeleton className="h-10 w-32" />
			</div>
			<div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
				{[1, 2, 3].map((i) => (
					<div key={i} className="space-y-2">
						<Skeleton className="h-4 w-24" />
						<Skeleton className="h-8 w-20" />
					</div>
				))}
			</div>
			<div className="space-y-3">
				<Skeleton className="h-4 w-32" />
				{[1, 2, 3].map((i) => (
					<Skeleton key={i} className="h-10 w-full" />
				))}
			</div>
		</div>
	)
}

export function SignalPanel({ projectId }: SignalPanelProps) {
	const {
		data: runsData,
		isLoading: runsLoading,
		error: runsError,
	} = useRuns(projectId, { limit: 3, enablePolling: true })

	const hasRunningRuns = runsData?.items.some(
		(run) => run.status === "running" || run.status === "pending",
	) ?? false

	const {
		data: perception,
		isLoading: perceptionLoading,
		error: perceptionError,
	} = usePerception(projectId, { enablePolling: hasRunningRuns })

	const isLoading = perceptionLoading || runsLoading
	const error = perceptionError || runsError

	const latestPoint =
		perception?.data && perception.data.length > 0
			? perception.data[perception.data.length - 1]
			: null

	const runCount = runsData?.total ?? 0
	const runs = runsData?.items ?? []

	if (isLoading) {
		return (
			<Card>
				<CardHeader>
					<CardTitle className="text-lg">Perception Overview</CardTitle>
				</CardHeader>
				<CardContent>
					<LoadingSkeleton />
				</CardContent>
			</Card>
		)
	}

	if (error) {
		return (
			<Card>
				<CardHeader>
					<CardTitle className="text-lg">Perception Overview</CardTitle>
				</CardHeader>
				<CardContent>
					<p className="text-sm text-destructive">
						Failed to load perception data. Please try again later.
					</p>
				</CardContent>
			</Card>
		)
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle className="text-lg">Perception Overview</CardTitle>
			</CardHeader>
			<CardContent className="space-y-6">
				{runCount === 0 ? (
					<EmptyState
						icon={<BarChart3 className="h-10 w-10" />}
						title="No monitoring data yet"
						description="Your first scan is on its way. Scores and trends will appear here once it completes."
					/>
				) : (
					<>
						<ScoreDisplay
							label="Overall Perception Score"
							value={latestPoint?.overall_score ?? null}
							format="score"
							trend={latestPoint?.trend_direction}
							className="text-center"
						/>

						<div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
							<ScoreDisplay
								label="Recommendation Share"
								value={latestPoint?.recommendation_share ?? null}
								format="percent"
							/>
							<ScoreDisplay
								label="Avg. Position"
								value={latestPoint?.position_avg ?? null}
								format="number"
							/>
							<ScoreDisplay
								label="Competitor Delta"
								value={latestPoint?.competitor_delta ?? null}
								format="score"
							/>
						</div>

						{runCount === 1 && (
							<p className="text-center text-xs text-muted-foreground">
								Baseline established. Trends will appear after your next scan.
							</p>
						)}
					</>
				)}

				<div>
					<h3 className="mb-3 text-sm font-semibold text-muted-foreground">
						Recent Runs
					</h3>
					{runs.length === 0 ? (
						<p className="text-sm text-muted-foreground">No runs yet.</p>
					) : (
						<div>
							{runs.map((run) => (
								<RunItem key={run.id} run={run} />
							))}
						</div>
					)}
				</div>
			</CardContent>
		</Card>
	)
}
