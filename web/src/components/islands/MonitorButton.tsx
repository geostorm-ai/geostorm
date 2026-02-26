import { useState } from "react"
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { useTriggerMonitoring } from "@/hooks/useProjects"
import { useRuns } from "@/hooks/useRuns"
import { useApiKeyStatus } from "@/hooks/useSettings"

interface MonitorButtonProps {
	projectId: string
	isDemo?: boolean
}

export function MonitorButton({ projectId, isDemo }: MonitorButtonProps) {
	const mutation = useTriggerMonitoring(projectId)
	const { data: apiKeyStatus } = useApiKeyStatus()
	const noApiKey = !isDemo && apiKeyStatus?.configured === false

	const { data: runsData } = useRuns(projectId, { limit: 1, enablePolling: true })
	const latestRun = runsData?.items?.[0]
	const isRunActive = latestRun?.status === "running" || latestRun?.status === "pending"

	const [dialogState, setDialogState] = useState<"closed" | "running" | "recent">("closed")

	function handleClick() {
		if (noApiKey) {
			window.location.assign("/settings")
			return
		}

		if (isRunActive) {
			setDialogState("running")
			return
		}

		if (latestRun) {
			const completedAt = latestRun.completed_at ? new Date(latestRun.completed_at).getTime() : 0
			const minutesSinceLastRun = (Date.now() - completedAt) / 60_000

			if (minutesSinceLastRun < 30) {
				setDialogState("recent")
				return
			}
		}

		mutation.mutate()
	}

	function handleConfirmRun() {
		setDialogState("closed")
		mutation.mutate()
	}

	return (
		<>
			<Button
				onClick={handleClick}
				disabled={mutation.isPending || isDemo || isRunActive}
				variant={noApiKey ? "outline" : "default"}
			>
				{mutation.isPending
					? "Starting..."
					: isRunActive
						? "Scan Running..."
						: noApiKey
							? "Configure API Key"
							: "Monitor Now"}
			</Button>

			<AlertDialog open={dialogState === "running"} onOpenChange={() => setDialogState("closed")}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Scan already in progress</AlertDialogTitle>
						<AlertDialogDescription>
							A monitoring scan is currently running. It needs to finish before you can start another one.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogAction onClick={() => setDialogState("closed")}>
							Got it
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>

			<AlertDialog open={dialogState === "recent"} onOpenChange={() => setDialogState("closed")}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Run another scan?</AlertDialogTitle>
						<AlertDialogDescription>
							A scan completed less than 30 minutes ago. Running again will incur API costs and is unlikely to show new results.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel>Cancel</AlertDialogCancel>
						<AlertDialogAction onClick={handleConfirmRun}>
							Run anyway
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</>
	)
}
