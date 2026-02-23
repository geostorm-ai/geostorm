import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"
import type { Term } from "@/schemas/project"

export function useTerms(projectId: string) {
	return useQuery({
		queryKey: ["terms", projectId],
		queryFn: () => apiFetch<Term[]>(`/projects/${projectId}/terms`),
		enabled: !!projectId,
	})
}

export function useCreateTerm(projectId: string) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (data: { name: string; description?: string | null }) =>
			apiFetch<Term>(`/projects/${projectId}/terms`, {
				method: "POST",
				body: JSON.stringify(data),
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["terms", projectId] })
			queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
		},
	})
}

export function useDeleteTerm(projectId: string) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (termId: string) =>
			apiFetch<void>(`/projects/${projectId}/terms/${termId}`, {
				method: "DELETE",
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["terms", projectId] })
			queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
		},
	})
}
