import { Play } from "lucide-react"
import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useTriggerMonitoring } from "@/hooks/useProjects"
import { useRuns } from "@/hooks/useRuns"
import { RUN_STATUS_COLORS } from "@/lib/constants"
import type { RunStatus } from "@/schemas/run"

interface RunsTableProps {
	projectId: string
	isDemo: boolean
}

export function RunsTable({ projectId, isDemo }: RunsTableProps) {
	const [limit, setLimit] = useState(20)
	const { data, isLoading } = useRuns(projectId, { limit })
	const triggerMonitoring = useTriggerMonitoring(projectId)

	const runs = data?.items ?? []
	const total = data?.total ?? 0
	const hasMore = runs.length < total

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
									{runs.map((run) => (
										<tr key={run.id} className="border-b last:border-0">
											<td className="py-2 pr-4">
												<Badge
													className={
														RUN_STATUS_COLORS[run.status as RunStatus] ?? ""
													}
												>
													{run.status}
												</Badge>
											</td>
											<td className="py-2 pr-4 capitalize">
												{run.trigger_type}
											</td>
											<td className="py-2 pr-4">
												{run.completed_queries}/{run.total_queries}
											</td>
											<td className="py-2 pr-4">
												{formatDate(run.started_at)}
											</td>
											<td className="py-2">{formatDate(run.completed_at)}</td>
										</tr>
									))}
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
	)
}
