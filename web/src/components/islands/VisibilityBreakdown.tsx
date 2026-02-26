import { useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { usePerceptionBreakdown } from "@/hooks/usePerceptionBreakdown"
import { useRuns } from "@/hooks/useRuns"

interface VisibilityBreakdownProps {
	projectId: string
}

function formatPercent(value: number): string {
	return `${Math.round(value * 100)}%`
}

function formatPosition(value: number | null): string {
	if (value === null) return "--"
	return `#${Math.round(value)}`
}

function TableSkeleton() {
	return (
		<div className="space-y-3">
			{[1, 2, 3].map((i) => (
				<div key={i} className="flex gap-4">
					<Skeleton className="h-4 w-40" />
					<Skeleton className="h-4 w-16" />
					<Skeleton className="h-4 w-16" />
				</div>
			))}
		</div>
	)
}

export function VisibilityBreakdown({ projectId }: VisibilityBreakdownProps) {
	const {
		data: runsData,
	} = useRuns(projectId, { limit: 1, enablePolling: false })

	const hasRunningRuns = runsData?.items.some(
		(run) => run.status === "running" || run.status === "pending",
	) ?? false

	const {
		data: breakdown,
		isLoading,
		error,
	} = usePerceptionBreakdown(projectId, { enablePolling: hasRunningRuns })

	const completedRunCount = runsData?.items.filter((r) => r.status === "completed").length ?? 0
	const hasMissingData = completedRunCount > 0 && (!breakdown || (breakdown.by_term.length === 0 && breakdown.by_provider.length === 0))
	const queryClient = useQueryClient()
	useEffect(() => {
		if (hasMissingData) {
			queryClient.invalidateQueries({ queryKey: ["perception-breakdown", projectId] })
		}
	}, [hasMissingData, projectId, queryClient])

	const runCount = runsData?.total ?? 0
	if (runCount === 0) return null

	const hasTermData = breakdown && breakdown.by_term.length > 0
	const hasProviderData = breakdown && breakdown.by_provider.length > 0

	if (!isLoading && !error && !hasTermData && !hasProviderData) return null

	return (
		<div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
			{/* By Search Term */}
			<Card>
				<CardHeader>
					<CardTitle className="text-lg">Results by Search Term</CardTitle>
				</CardHeader>
				<CardContent>
					{isLoading && <TableSkeleton />}
					{error && (
						<p className="text-sm text-destructive">
							Failed to load breakdown data.
						</p>
					)}
					{!isLoading && !error && hasTermData && (
						<div className="overflow-x-auto">
							<table className="w-full text-sm">
								<thead>
									<tr className="border-b text-left text-muted-foreground">
										<th className="pb-2 pr-4 font-medium">Search Term</th>
										<th className="pb-2 pr-4 font-medium">Mentioned</th>
										<th className="pb-2 font-medium">Avg. Ranking</th>
									</tr>
								</thead>
								<tbody>
									{breakdown.by_term.map((term) => (
										<tr key={term.term_id} className="border-b last:border-b-0">
											<td className="py-2 pr-4 font-medium">{term.term_name}</td>
											<td className="py-2 pr-4">{formatPercent(term.recommendation_share)}</td>
											<td className="py-2">{formatPosition(term.position_avg)}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}
					{!isLoading && !error && !hasTermData && (
						<p className="text-sm text-muted-foreground">No term-level data available yet.</p>
					)}
				</CardContent>
			</Card>

			{/* By AI Model */}
			<Card>
				<CardHeader>
					<CardTitle className="text-lg">Results by AI Model</CardTitle>
				</CardHeader>
				<CardContent>
					{isLoading && <TableSkeleton />}
					{error && (
						<p className="text-sm text-destructive">
							Failed to load breakdown data.
						</p>
					)}
					{!isLoading && !error && hasProviderData && (
						<div className="overflow-x-auto">
							<table className="w-full text-sm">
								<thead>
									<tr className="border-b text-left text-muted-foreground">
										<th className="pb-2 pr-4 font-medium">AI Model</th>
										<th className="pb-2 pr-4 font-medium">Mentioned</th>
										<th className="pb-2 font-medium">Avg. Ranking</th>
									</tr>
								</thead>
								<tbody>
									{breakdown.by_provider.map((provider) => (
										<tr key={provider.provider_name} className="border-b last:border-b-0">
											<td className="py-2 pr-4 font-medium">{provider.provider_name}</td>
											<td className="py-2 pr-4">{formatPercent(provider.recommendation_share)}</td>
											<td className="py-2">{formatPosition(provider.position_avg)}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}
					{!isLoading && !error && !hasProviderData && (
						<p className="text-sm text-muted-foreground">No provider-level data available yet.</p>
					)}
				</CardContent>
			</Card>
		</div>
	)
}
