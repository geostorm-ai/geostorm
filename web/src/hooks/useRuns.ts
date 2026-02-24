import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"
import type { Response, Run, RunDetail } from "@/schemas/run"
import type { PaginatedResponse } from "@/schemas/shared"

export function useRuns(
	projectId: string,
	options?: { limit?: number; offset?: number; status?: string; enablePolling?: boolean },
) {
	const params = new URLSearchParams()
	if (options?.limit) params.set("limit", String(options.limit))
	if (options?.offset) params.set("offset", String(options.offset))
	if (options?.status) params.set("status", options.status)
	const qs = params.toString()
	return useQuery({
		queryKey: ["runs", projectId, options],
		queryFn: () =>
			apiFetch<PaginatedResponse<Run>>(
				`/projects/${projectId}/runs${qs ? `?${qs}` : ""}`,
			),
		enabled: !!projectId,
		refetchInterval: options?.enablePolling
			? (query) => {
					const data = query.state.data as PaginatedResponse<Run> | undefined
					if (data?.items.some((run) => run.status === "running" || run.status === "pending")) {
						return 3000
					}
					return false
				}
			: undefined,
	})
}

export function useRun(runId: string) {
	return useQuery({
		queryKey: ["runs", "detail", runId],
		queryFn: () => apiFetch<RunDetail>(`/runs/${runId}`),
		enabled: !!runId,
	})
}

export function useRunResponses(
	runId: string,
	options?: { limit?: number; offset?: number },
) {
	const params = new URLSearchParams()
	if (options?.limit) params.set("limit", String(options.limit))
	if (options?.offset) params.set("offset", String(options.offset))
	const qs = params.toString()
	return useQuery({
		queryKey: ["runs", runId, "responses", options],
		queryFn: () =>
			apiFetch<PaginatedResponse<Response>>(
				`/runs/${runId}/responses${qs ? `?${qs}` : ""}`,
			),
		enabled: !!runId,
	})
}
