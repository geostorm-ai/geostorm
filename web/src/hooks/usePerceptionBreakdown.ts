import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"
import type { PerceptionBreakdownResponse } from "@/schemas/breakdown"

export function usePerceptionBreakdown(
	projectId: string,
	options?: { enablePolling?: boolean },
) {
	return useQuery({
		queryKey: ["perception-breakdown", projectId],
		queryFn: () =>
			apiFetch<PerceptionBreakdownResponse>(
				`/projects/${projectId}/perception/breakdown`,
			),
		enabled: !!projectId,
		refetchInterval: options?.enablePolling ? 5000 : undefined,
	})
}
