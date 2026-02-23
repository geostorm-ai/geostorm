import { Button } from "@/components/ui/button"
import { useTriggerMonitoring } from "@/hooks/useProjects"

interface MonitorButtonProps {
	projectId: string
	isDemo?: boolean
}

export function MonitorButton({ projectId, isDemo }: MonitorButtonProps) {
	const mutation = useTriggerMonitoring(projectId)

	return (
		<Button
			onClick={() => mutation.mutate()}
			disabled={mutation.isPending || isDemo}
		>
			{mutation.isPending ? "Running..." : "Monitor Now"}
		</Button>
	)
}
