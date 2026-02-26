import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { RunProgressPipeline } from "@/components/RunProgressPipeline"
import { Skeleton } from "@/components/ui/skeleton"
import { useRuns } from "@/hooks/useRuns"
import { useRunProgress } from "@/hooks/useRunProgress"
import { cn } from "@/lib/utils"
import { getRunDisplay } from "@/lib/runs"
import type { Run } from "@/schemas/run"

interface RecentRunsProps {
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

function ActiveRunProgress({ runId }: { runId: string }) {
	const progress = useRunProgress(runId)

	if (!progress) {
		return <Skeleton className="h-[230px] w-full" />
	}

	return <RunProgressPipeline progress={progress} />
}

export function RecentRuns({ projectId }: RecentRunsProps) {
	const {
		data: runsData,
		isLoading,
		error,
	} = useRuns(projectId, { limit: 3, enablePolling: true })

	const runs = runsData?.items ?? []
	const activeRun = runs.find(
		(run) => run.status === "running" || run.status === "pending",
	)
	const pastRuns = runs.filter((run) => run.id !== activeRun?.id)

	if (isLoading) {
		return (
			<Card>
				<CardHeader>
					<CardTitle className="text-lg">Recent Runs</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="space-y-3">
						{[1, 2, 3].map((i) => (
							<Skeleton key={i} className="h-10 w-full" />
						))}
					</div>
				</CardContent>
			</Card>
		)
	}

	if (error) {
		return (
			<Card>
				<CardHeader>
					<CardTitle className="text-lg">Recent Runs</CardTitle>
				</CardHeader>
				<CardContent>
					<p className="text-sm text-destructive">
						Failed to load runs. Please try again later.
					</p>
				</CardContent>
			</Card>
		)
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle className="text-lg">Recent Runs</CardTitle>
			</CardHeader>
			<CardContent>
				{runs.length === 0 ? (
					<p className="text-sm text-muted-foreground">
						Your first scan is starting. Run status will appear here momentarily.
					</p>
				) : (
					<div className="space-y-4">
						{activeRun && <ActiveRunProgress runId={activeRun.id} />}
						{pastRuns.length > 0 && (
							<div>
								{pastRuns.map((run) => (
									<RunItem key={run.id} run={run} />
								))}
							</div>
						)}
					</div>
				)}
			</CardContent>
		</Card>
	)
}
