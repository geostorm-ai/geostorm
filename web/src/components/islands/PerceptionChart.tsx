import { useMemo, useState } from "react"
import {
	Bar,
	BarChart,
	CartesianGrid,
	Legend,
	Line,
	LineChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts"
import { EmptyState } from "@/components/EmptyState"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { usePerception } from "@/hooks/usePerception"
import { usePerceptionBreakdown } from "@/hooks/usePerceptionBreakdown"
import { LineChart as LineChartIcon } from "lucide-react"

interface PerceptionChartProps {
	projectId: string
	runCount?: number
}

const RANGE_OPTIONS = [
	{ label: "7d", days: 7 },
	{ label: "30d", days: 30 },
	{ label: "90d", days: 90 },
] as const

function formatDate(dateStr: string): string {
	const date = new Date(dateStr)
	return date.toLocaleDateString(undefined, {
		month: "short",
		day: "numeric",
	})
}

function getDateRange(days: number): { startDate: string; endDate: string } {
	const now = new Date()
	// Truncate to date-only to produce stable keys across re-renders
	const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`
	const start = new Date(todayStr)
	start.setDate(start.getDate() - days)
	return {
		startDate: start.toISOString().split("T")[0],
		endDate: todayStr,
	}
}

function LoadingSkeleton() {
	return (
		<div className="space-y-4">
			<div className="flex gap-2">
				{[1, 2, 3].map((i) => (
					<Skeleton key={i} className="h-8 w-12" />
				))}
			</div>
			<Skeleton className="h-64 w-full" />
		</div>
	)
}

function FirstRunBarChart({ projectId }: { projectId: string }) {
	const { data: breakdown, isLoading } = usePerceptionBreakdown(projectId)

	const barData = useMemo(() => {
		if (!breakdown?.by_term) return []
		return breakdown.by_term.map((term) => ({
			name: term.term_name,
			"Mention Rate": Math.round(term.recommendation_share * 100),
		}))
	}, [breakdown])

	if (isLoading) return <Skeleton className="h-64 w-full" />
	if (barData.length === 0) {
		return (
			<EmptyState
				icon={<LineChartIcon className="h-10 w-10" />}
				title="No term-level data yet"
				description="Per-term visibility will appear after your first scan completes."
			/>
		)
	}

	return (
		<div className="space-y-2">
			<p className="text-sm text-muted-foreground">
				AI Mention Rate by Search Term (% of responses that mention your brand)
			</p>
			<ResponsiveContainer width="100%" height={Math.max(200, barData.length * 50 + 60)}>
				<BarChart data={barData} layout="vertical" margin={{ left: 20, right: 20 }}>
					<CartesianGrid strokeDasharray="3 3" className="opacity-30" horizontal={false} />
					<XAxis type="number" domain={[0, 100]} tick={{ fontSize: 12 }} unit="%" />
					<YAxis
						type="category"
						dataKey="name"
						tick={{ fontSize: 12 }}
						width={150}
						tickLine={false}
						axisLine={false}
					/>
					<Tooltip formatter={(value) => [`${value ?? 0}%`, "Mention Rate"]} />
					<Bar dataKey="Mention Rate" fill="#3b82f6" radius={[0, 4, 4, 0]} />
				</BarChart>
			</ResponsiveContainer>
		</div>
	)
}

export function PerceptionChart({ projectId, runCount }: PerceptionChartProps) {
	const [rangeDays, setRangeDays] = useState(30)

	const { startDate, endDate } = useMemo(
		() => getDateRange(rangeDays),
		[rangeDays],
	)

	const { data, isLoading, error } = usePerception(projectId, {
		startDate,
		endDate,
	})

	const chartData = useMemo(() => {
		if (!data?.data) return []
		return data.data.map((point) => ({
			date: formatDate(point.date),
			"Overall Score": point.overall_score,
			"Mention Rate":
				point.recommendation_share !== null
					? Math.round(point.recommendation_share * 100)
					: null,
		}))
	}, [data])

	const isFirstRun = runCount === 1

	return (
		<Card>
			<CardHeader>
				<div className="flex items-center justify-between">
					<div>
						<CardTitle className="text-lg">Perception Over Time</CardTitle>
						{!isFirstRun && chartData.length > 0 && (
							<p className="mt-1 text-xs text-muted-foreground">
								Scores range from 0-100. Higher means more AI visibility.
							</p>
						)}
					</div>
					{!isFirstRun && (
						<div className="flex gap-1">
							{RANGE_OPTIONS.map((option) => (
								<Button
									key={option.days}
									variant={rangeDays === option.days ? "default" : "outline"}
									size="sm"
									onClick={() => setRangeDays(option.days)}
								>
									{option.label}
								</Button>
							))}
						</div>
					)}
				</div>
			</CardHeader>
			<CardContent>
				{isLoading && <LoadingSkeleton />}

				{error && (
					<p className="text-sm text-destructive">
						Failed to load perception data. Please try again later.
					</p>
				)}

				{/* First run: show bar chart of per-term visibility */}
				{!isLoading && !error && isFirstRun && (
					<FirstRunBarChart projectId={projectId} />
				)}

				{/* No runs yet */}
				{!isLoading && !error && !runCount && (
					<EmptyState
						icon={<LineChartIcon className="h-10 w-10" />}
						title="No monitoring data yet"
						description="Charts will appear after your first scan."
					/>
				)}

				{/* Multiple runs but no data in range */}
				{!isLoading && !error && !isFirstRun && runCount && runCount > 1 && chartData.length === 0 && (
					<EmptyState
						icon={<LineChartIcon className="h-10 w-10" />}
						title="No data for this period"
						description="Try selecting a different date range."
					/>
				)}

				{/* Multiple runs with data: line chart */}
				{!isLoading && !error && !isFirstRun && chartData.length > 0 && (
					<ResponsiveContainer width="100%" height={320}>
						<LineChart data={chartData}>
							<CartesianGrid strokeDasharray="3 3" className="opacity-30" />
							<XAxis
								dataKey="date"
								tick={{ fontSize: 12 }}
								tickLine={false}
								axisLine={false}
							/>
							<YAxis
								domain={[0, 100]}
								tick={{ fontSize: 12 }}
								tickLine={false}
								axisLine={false}
								label={{ value: "Score (0-100)", angle: -90, position: "insideLeft", style: { fontSize: 11, fill: "#9ca3af" } }}
							/>
							<Tooltip />
							<Legend />
							<Line
								type="monotone"
								dataKey="Overall Score"
								stroke="#3b82f6"
								strokeWidth={2}
								dot={false}
								connectNulls
							/>
							<Line
								type="monotone"
								dataKey="Mention Rate"
								stroke="#22c55e"
								strokeWidth={2}
								dot={false}
								connectNulls
							/>
						</LineChart>
					</ResponsiveContainer>
				)}
			</CardContent>
		</Card>
	)
}
