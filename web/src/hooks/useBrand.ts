import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"
import type { Brand } from "@/schemas/project"

export function useBrand(projectId: string) {
	return useQuery({
		queryKey: ["brand", projectId],
		queryFn: () => apiFetch<Brand>(`/projects/${projectId}/brand`),
		enabled: !!projectId,
	})
}

export function useUpdateBrand(projectId: string) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (data: {
			name?: string
			aliases?: string[]
			description?: string | null
			website?: string | null
		}) =>
			apiFetch<Brand>(`/projects/${projectId}/brand`, {
				method: "PUT",
				body: JSON.stringify(data),
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["brand", projectId] })
			queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
		},
	})
}
