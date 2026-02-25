import { Button } from "@/components/ui/button"
import { useTriggerMonitoring } from "@/hooks/useProjects"
import { useApiKeyStatus } from "@/hooks/useSettings"

interface MonitorButtonProps {
	projectId: string
	isDemo?: boolean
}

export function MonitorButton({ projectId, isDemo }: MonitorButtonProps) {
	const mutation = useTriggerMonitoring(projectId)
	const { data: apiKeyStatus } = useApiKeyStatus()
	const noApiKey = !isDemo && apiKeyStatus?.configured === false

	return (
		<Button
			onClick={() => noApiKey ? window.location.assign("/settings") : mutation.mutate()}
			disabled={mutation.isPending || isDemo}
			variant={noApiKey ? "outline" : "default"}
		>
			{mutation.isPending ? "Running..." : noApiKey ? "Configure API Key" : "Monitor Now"}
		</Button>
	)
}
