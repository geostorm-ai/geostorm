import { Play } from "lucide-react"
import { Fragment, useState } from "react"
import { ResponseViewer } from "@/components/islands/ResponseViewer"
import { RunProgressPipeline } from "@/components/RunProgressPipeline"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { useTriggerMonitoring } from "@/hooks/useProjects"
import { useRuns } from "@/hooks/useRuns"
import { useRunProgress } from "@/hooks/useRunProgress"
import { getRunDisplay } from "@/lib/runs"

interface RunsTableProps {
	projectId: string
	isDemo: boolean
}

export function RunsTable({ projectId, isDemo }: RunsTableProps) {
	const [limit, setLimit] = useState(20)
	const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
	const { data, isLoading } = useRuns(projectId, { limit, enablePolling: true })
	const triggerMonitoring = useTriggerMonitoring(projectId)

	const runs = data?.items ?? []
	const total = data?.total ?? 0
	const hasMore = runs.length < total

	// Find the first running run for SSE progress
	const runningRun = runs.find(
		(r) => r.status === "running" || r.status === "pending",
	)
	const progress = useRunProgress(runningRun?.id, !!runningRun)

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return "-"
		return new Date(dateStr).toLocaleString([], {
			month: "short",
			day: "numeric",
			hour: "numeric",
			minute: "2-digit",
		})
	}

	if (isLoading) {
		return (
			<Card>
				<CardHeader>
					<CardTitle>Monitoring Runs</CardTitle>
				</CardHeader>
				<CardContent className="space-y-3">
					{Array.from({ length: 5 }).map((_, i) => (
						<Skeleton
							key={`run-skeleton-${i.toString()}`}
							className="h-10 w-full"
						/>
					))}
				</CardContent>
			</Card>
		)
	}

	return (
		<>
			<Card>
				<CardHeader>
					<div className="flex items-center justify-between">
						<CardTitle>Monitoring Runs</CardTitle>
						<Button
							size="sm"
							onClick={() => triggerMonitoring.mutate()}
							disabled={isDemo || triggerMonitoring.isPending}
						>
							<Play className="mr-1 h-4 w-4" />
							{triggerMonitoring.isPending ? "Starting..." : "Monitor Now"}
						</Button>
					</div>
				</CardHeader>
				<CardContent>
					{runs.length === 0 ? (
						<p className="py-8 text-center text-sm text-muted-foreground">
							No monitoring runs yet
						</p>
					) : (
						<div className="space-y-4">
							<div className="overflow-x-auto">
								<table className="w-full text-sm">
									<thead>
										<tr className="border-b text-left">
											<th className="pb-2 pr-4 font-medium">Status</th>
											<th className="pb-2 pr-4 font-medium">Trigger</th>
											<th className="pb-2 pr-4 font-medium">Queries</th>
											<th className="pb-2 pr-4 font-medium">Started</th>
											<th className="pb-2 font-medium">Completed</th>
										</tr>
									</thead>
									<tbody>
										{runs.map((run) => {
											const { displayStatus, statusColor, isPartial } = getRunDisplay(run)
											const isRunning = run.status === "running" || run.status === "pending"
											const showPipeline = isRunning && progress && progress.run_id === run.id

											// Use SSE counts when available, fall back to DB-polled values
											const completed = showPipeline ? progress.completed : run.completed_queries
											const failed = showPipeline ? progress.failed : run.failed_queries

											return (
												<Fragment key={run.id}>
													<tr
														className="border-b last:border-0 cursor-pointer hover:bg-accent/50 transition-colors"
														onClick={() => setSelectedRunId(run.id)}
													>
														<td className="py-2 pr-4">
															<Badge className={statusColor}>
																{displayStatus}
															</Badge>
														</td>
														<td className="py-2 pr-4 capitalize">
															{run.trigger_type}
														</td>
														<td className="py-2 pr-4">
															{completed}/{run.total_queries}
															{isPartial && (
																<span className="ml-1 text-amber-600 dark:text-amber-400">
																	({failed} failed)
																</span>
															)}
														</td>
														<td className="py-2 pr-4">
															{formatDate(run.started_at)}
														</td>
														<td className="py-2">{formatDate(run.completed_at)}</td>
													</tr>
													{showPipeline && (
														<tr className="border-b last:border-0">
															<td colSpan={5} className="py-3 px-2">
																<RunProgressPipeline progress={progress} />
															</td>
														</tr>
													)}
												</Fragment>
											)
										})}
									</tbody>
								</table>
							</div>

							{hasMore && (
								<div className="flex justify-center">
									<Button
										variant="outline"
										size="sm"
										onClick={() => setLimit((prev) => prev + 20)}
									>
										Load more
									</Button>
								</div>
							)}
						</div>
					)}
				</CardContent>
			</Card>

			<Sheet open={!!selectedRunId} onOpenChange={(open) => !open && setSelectedRunId(null)}>
				<SheetContent side="right" className="w-full sm:max-w-xl overflow-y-auto">
					<SheetHeader>
						<SheetTitle>Run Responses</SheetTitle>
						<SheetDescription>
							LLM responses from this monitoring run
						</SheetDescription>
					</SheetHeader>
					<div className="mt-4">
						{selectedRunId && <ResponseViewer runId={selectedRunId} />}
					</div>
				</SheetContent>
			</Sheet>
		</>
	)
}
