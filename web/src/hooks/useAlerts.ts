import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"
import type { Alert } from "@/schemas/alert"
import type { PaginatedResponse } from "@/schemas/shared"

export function useAlerts(
	projectId: string,
	options?: { acknowledged?: boolean },
) {
	const params = new URLSearchParams({ project_id: projectId })
	if (options?.acknowledged !== undefined) {
		params.set("acknowledged", String(options.acknowledged))
	}
	return useQuery({
		queryKey: ["alerts", projectId, options],
		queryFn: () =>
			apiFetch<PaginatedResponse<Alert>>(`/alerts?${params.toString()}`),
		enabled: !!projectId,
		refetchInterval: 60_000,
	})
}

export function useAcknowledgeAlert() {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (alertId: string) =>
			apiFetch<{ status: string }>(`/alerts/${alertId}/acknowledge`, {
				method: "POST",
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["alerts"] })
		},
	})
}
