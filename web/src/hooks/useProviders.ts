import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"

interface LLMProvider {
	id: string
	project_id: string
	provider_name: string
	model_name: string
	is_enabled: boolean
	created_at: string
	updated_at: string
}

export function useProviders(projectId: string) {
	return useQuery({
		queryKey: ["providers", projectId],
		queryFn: () => apiFetch<LLMProvider[]>(`/projects/${projectId}/providers`),
		enabled: !!projectId,
	})
}

export function useCreateProvider(projectId: string) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (data: { provider_name: string; model_name: string }) =>
			apiFetch<LLMProvider>(`/projects/${projectId}/providers`, {
				method: "POST",
				body: JSON.stringify(data),
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["providers", projectId] })
		},
	})
}

export function useUpdateProvider(projectId: string) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: ({
			providerId,
			...data
		}: {
			providerId: string
			is_enabled?: boolean
			model_name?: string
		}) =>
			apiFetch<LLMProvider>(
				`/projects/${projectId}/providers/${providerId}`,
				{
					method: "PATCH",
					body: JSON.stringify(data),
				},
			),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["providers", projectId] })
		},
	})
}

export function useDeleteProvider(projectId: string) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (providerId: string) =>
			apiFetch<void>(`/projects/${projectId}/providers/${providerId}`, {
				method: "DELETE",
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["providers", projectId] })
		},
	})
}
