import { useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { EmptyState } from "@/components/EmptyState"
import { ScoreDisplay } from "@/components/ScoreDisplay"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { usePerception } from "@/hooks/usePerception"
import { usePerceptionBreakdown } from "@/hooks/usePerceptionBreakdown"
import { useRuns } from "@/hooks/useRuns"
import { BarChart3 } from "lucide-react"

interface SignalPanelProps {
	projectId: string
}

function LoadingSkeleton() {
	return (
		<div className="space-y-6">
			<div className="flex flex-col gap-2">
				<Skeleton className="h-4 w-48" />
				<Skeleton className="h-6 w-64" />
			</div>
			<div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
				{[1, 2, 3].map((i) => (
					<div key={i} className="space-y-2">
						<Skeleton className="h-4 w-24" />
						<Skeleton className="h-8 w-20" />
					</div>
				))}
			</div>
		</div>
	)
}

function formatMentionHeadline(
	breakdown: { total_responses: number; brand_mentions: number } | null,
	latestShare: number | null,
	previousShare: number | null,
	isFirstRun: boolean,
): string {
	if (!breakdown || breakdown.total_responses === 0) {
		return "No AI responses analyzed yet"
	}
	const { total_responses, brand_mentions } = breakdown
	const pct = Math.round((brand_mentions / total_responses) * 100)
	let headline = `Your brand was mentioned in ${brand_mentions} of ${total_responses} AI responses (${pct}%)`
	if (!isFirstRun && latestShare !== null && previousShare !== null) {
		const prevPct = Math.round(previousShare * 100)
		const curPct = Math.round(latestShare * 100)
		if (curPct > prevPct) {
			headline += `, up from ${prevPct}%`
		} else if (curPct < prevPct) {
			headline += `, down from ${prevPct}%`
		}
	}
	return headline
}


function CompetitorDelta({ delta }: { delta: number | null }) {
	if (delta === null) {
		return (
			<div className="flex flex-col gap-1">
				<span className="text-sm text-muted-foreground">vs. Top Competitor</span>
				<span className="text-3xl font-bold tracking-tight">--</span>
				<span className="text-xs text-muted-foreground">Not enough data yet</span>
			</div>
		)
	}
	const absPct = Math.abs(Math.round(delta * 100))
	const isAhead = delta > 0
	const isTied = absPct === 0
	return (
		<div className="flex flex-col gap-1">
			<span className="text-sm text-muted-foreground">vs. Top Competitor</span>
			<span className={`text-lg font-semibold ${isAhead ? "text-green-600 dark:text-green-400" : isTied ? "text-muted-foreground" : "text-red-600 dark:text-red-400"}`}>
				{isTied
					? "Tied with top competitor"
					: isAhead
						? `Mentioned ${absPct}% more often`
						: `Mentioned ${absPct}% less often`}
			</span>
			<span className="text-xs text-muted-foreground">Compared to your closest rival&apos;s mention rate</span>
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

	const {
		data: breakdown,
		isLoading: breakdownLoading,
	} = usePerceptionBreakdown(projectId, { enablePolling: hasRunningRuns })

	// When a run just finished but perception data hasn't arrived yet,
	// the cached empty response leaves the panel showing "--".
	// Invalidate perception so it refetches with the new scores.
	const completedRunCount = runsData?.items.filter((r) => r.status === "completed").length ?? 0
	const hasMissingScores = completedRunCount > 0 && (!perception?.data || perception.data.length === 0)
	const queryClient = useQueryClient()
	useEffect(() => {
		if (hasMissingScores) {
			queryClient.invalidateQueries({ queryKey: ["perception", projectId] })
			queryClient.invalidateQueries({ queryKey: ["perception-breakdown", projectId] })
		}
	}, [hasMissingScores, projectId, queryClient])

	const isLoading = perceptionLoading || runsLoading || breakdownLoading
	const error = perceptionError || runsError

	const latestPoint =
		perception?.data && perception.data.length > 0
			? perception.data[perception.data.length - 1]
			: null

	const previousPoint =
		perception?.data && perception.data.length > 1
			? perception.data[perception.data.length - 2]
			: null

	const runCount = runsData?.total ?? 0
	const isFirstRun = runCount <= 1
	const showTrend = (dir: string | undefined) => !isFirstRun && dir && dir !== "stable"

	if (isLoading) {
		return (
			<Card>
				<CardHeader>
					<CardTitle className="text-lg">AI Visibility Report</CardTitle>
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
					<CardTitle className="text-lg">AI Visibility Report</CardTitle>
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
				<CardTitle className="text-lg">AI Visibility Report</CardTitle>
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
						{/* Headline: plain-English summary */}
						<div className="space-y-2">
							<p className="text-base font-medium">
								{formatMentionHeadline(
									breakdown ?? null,
									latestPoint?.recommendation_share ?? null,
									previousPoint?.recommendation_share ?? null,
									isFirstRun,
								)}
							</p>
							<p className="text-sm text-muted-foreground">
								Visibility Score: {latestPoint?.overall_score !== null && latestPoint?.overall_score !== undefined
									? `${Math.round(latestPoint.overall_score)} / 100`
									: "--"
								}
								{" "}<span className="text-xs">&mdash; based on mention rate, ranking position, and competitor comparison</span>
							</p>
						</div>

						{/* Three metric cards with clear labels */}
						<div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
							<ScoreDisplay
								label="AI Mention Rate"
								value={latestPoint?.recommendation_share ?? null}
								format="percent"
								trend={showTrend(latestPoint?.trend_direction) ? latestPoint?.trend_direction : undefined}
								description="How often AI recommends you"
							/>
							<ScoreDisplay
								label="Avg. Ranking"
								value={latestPoint?.position_avg ?? null}
								format="number"
								description="Your typical spot in recommendation lists (lower is better)"
							/>
							<CompetitorDelta delta={latestPoint?.competitor_delta ?? null} />
						</div>

						{isFirstRun && (
							<p className="text-center text-xs text-muted-foreground">
								Run another scan to start tracking changes over time.
							</p>
						)}
					</>
				)}
			</CardContent>
		</Card>
	)
}
