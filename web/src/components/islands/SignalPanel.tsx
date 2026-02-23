import { ScoreDisplay } from "@/components/ScoreDisplay"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { usePerception } from "@/hooks/usePerception"
import { useRuns } from "@/hooks/useRuns"
import { RUN_STATUS_COLORS } from "@/lib/constants"
import { cn } from "@/lib/utils"
import type { Run } from "@/schemas/run"

interface SignalPanelProps {
	projectId: string
}

function RunItem({ run }: { run: Run }) {
	const statusColor = RUN_STATUS_COLORS[run.status] ?? RUN_STATUS_COLORS.pending

	return (
		<div className="flex items-center justify-between border-b py-3 last:border-b-0">
			<div className="flex items-center gap-3">
				<Badge variant="secondary" className={cn(statusColor)}>
					{run.status}
				</Badge>
				<span className="text-sm text-muted-foreground">
					{new Date(run.created_at).toLocaleDateString()}
				</span>
			</div>
			<span className="text-xs text-muted-foreground">
				{run.completed_queries}/{run.total_queries} queries
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
		data: perception,
		isLoading: perceptionLoading,
		error: perceptionError,
	} = usePerception(projectId)
	const {
		data: runsData,
		isLoading: runsLoading,
		error: runsError,
	} = useRuns(projectId, { limit: 3 })

	const isLoading = perceptionLoading || runsLoading
	const error = perceptionError || runsError

	const latestPoint =
		perception?.data && perception.data.length > 0
			? perception.data[perception.data.length - 1]
			: null

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
