import { useMemo, useState } from "react"
import {
	CartesianGrid,
	Legend,
	Line,
	LineChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { usePerception } from "@/hooks/usePerception"

interface PerceptionChartProps {
	projectId: string
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

export function PerceptionChart({ projectId }: PerceptionChartProps) {
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
			"Recommendation Share":
				point.recommendation_share !== null
					? Math.round(point.recommendation_share * 100)
					: null,
		}))
	}, [data])

	return (
		<Card>
			<CardHeader>
				<div className="flex items-center justify-between">
					<CardTitle className="text-lg">Perception Over Time</CardTitle>
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
				</div>
			</CardHeader>
			<CardContent>
				{isLoading && <LoadingSkeleton />}

				{error && (
					<p className="text-sm text-destructive">
						Failed to load perception data. Please try again later.
					</p>
				)}

				{!isLoading && !error && chartData.length === 0 && (
					<p className="py-12 text-center text-sm text-muted-foreground">
						No perception data available for this period.
					</p>
				)}

				{!isLoading && !error && chartData.length > 0 && (
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
								dataKey="Recommendation Share"
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
