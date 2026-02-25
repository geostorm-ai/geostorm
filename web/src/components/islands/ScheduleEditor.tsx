import { AlertCircle, Check } from "lucide-react"
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { useSchedule, useUpdateSchedule } from "@/hooks/useSchedule"
import { DAY_NAMES } from "@/lib/constants"

interface ScheduleEditorProps {
	projectId: string
	isDemo: boolean
}

function formatHour(hour: number): string {
	return new Date(0, 0, 0, hour).toLocaleTimeString([], {
		hour: "numeric",
		hour12: true,
	})
}

export function ScheduleEditor({ projectId, isDemo }: ScheduleEditorProps) {
	const { data: schedule, isLoading } = useSchedule(projectId)
	const updateSchedule = useUpdateSchedule(projectId)
	const [hourOfDay, setHourOfDay] = useState(9)
	const [daysOfWeek, setDaysOfWeek] = useState<number[]>([0, 1, 2, 3, 4])
	const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">(
		"idle",
	)

	useEffect(() => {
		if (schedule) {
			setHourOfDay(schedule.hour_of_day)
			setDaysOfWeek(schedule.days_of_week)
		}
	}, [schedule])

	function toggleDay(dayIndex: number) {
		setDaysOfWeek((prev) =>
			prev.includes(dayIndex)
				? prev.filter((d) => d !== dayIndex)
				: [...prev, dayIndex].sort(),
		)
	}

	function handleSave() {
		setSaveStatus("idle")
		updateSchedule.mutate(
			{ hour_of_day: hourOfDay, days_of_week: daysOfWeek },
			{
				onSuccess: () => {
					setSaveStatus("success")
					setTimeout(() => setSaveStatus("idle"), 3000)
				},
				onError: () => {
					setSaveStatus("error")
					setTimeout(() => setSaveStatus("idle"), 3000)
				},
			},
		)
	}

	if (isLoading) {
		return (
			<Card>
				<CardHeader>
					<CardTitle>Monitoring Schedule</CardTitle>
				</CardHeader>
				<CardContent className="space-y-4">
					<Skeleton className="h-10 w-48" />
					<div className="flex gap-2">
						{Array.from({ length: 7 }).map((_, i) => (
							<Skeleton
								key={`day-skeleton-${i.toString()}`}
								className="h-8 w-20"
							/>
						))}
					</div>
				</CardContent>
			</Card>
		)
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle>Monitoring Schedule</CardTitle>
			</CardHeader>
			<CardContent className="space-y-6">
				{isDemo && (
					<div className="flex items-center gap-2 rounded-md bg-blue-50 p-3 text-sm text-blue-700 dark:bg-blue-950 dark:text-blue-300">
						<AlertCircle className="h-4 w-4 shrink-0" />
						Read-only demo project
					</div>
				)}

				<div className="space-y-2">
					<Label>Time of Day</Label>
					<Select
						value={String(hourOfDay)}
						onValueChange={(v) => setHourOfDay(Number(v))}
						disabled={isDemo}
					>
						<SelectTrigger className="w-48">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							{Array.from({ length: 24 }).map((_, hour) => (
								<SelectItem
									key={`hour-${hour.toString()}`}
									value={String(hour)}
								>
									{formatHour(hour)}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
					<p className="text-xs text-muted-foreground">Times are in UTC</p>
				</div>

				<div className="space-y-2">
					<Label>Days of Week</Label>
					<div className="flex flex-wrap gap-4">
						{DAY_NAMES.map((dayName, index) => (
							<div key={dayName} className="flex items-center gap-2">
								<Checkbox
									id={`day-${index.toString()}`}
									checked={daysOfWeek.includes(index)}
									onCheckedChange={() => toggleDay(index)}
									disabled={isDemo}
								/>
								<Label
									htmlFor={`day-${index.toString()}`}
									className="cursor-pointer text-sm font-normal"
								>
									{dayName}
								</Label>
							</div>
						))}
					</div>
				</div>

				<div className="flex items-center gap-3">
					<Button
						onClick={handleSave}
						disabled={isDemo || updateSchedule.isPending}
					>
						{updateSchedule.isPending ? "Saving..." : "Save"}
					</Button>
					{saveStatus === "success" && (
						<span className="flex items-center gap-1 text-sm text-green-600 dark:text-green-400">
							<Check className="h-4 w-4" />
							Schedule saved
						</span>
					)}
					{saveStatus === "error" && (
						<span className="text-sm text-destructive">
							Failed to save schedule
						</span>
					)}
				</div>
			</CardContent>
		</Card>
	)
}
