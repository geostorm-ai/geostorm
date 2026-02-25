import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"
import type { PerceptionResponse } from "@/schemas/perception"

export function usePerception(
	projectId: string,
	options?: { startDate?: string; endDate?: string; enablePolling?: boolean },
) {
	const params = new URLSearchParams()
	if (options?.startDate) params.set("start_date", options.startDate)
	if (options?.endDate) params.set("end_date", options.endDate)
	const qs = params.toString()
	return useQuery({
		queryKey: ["perception", projectId, { startDate: options?.startDate, endDate: options?.endDate }],
		queryFn: () =>
			apiFetch<PerceptionResponse>(
				`/projects/${projectId}/perception${qs ? `?${qs}` : ""}`,
			),
		enabled: !!projectId,
		refetchInterval: options?.enablePolling ? 5000 : undefined,
	})
}
