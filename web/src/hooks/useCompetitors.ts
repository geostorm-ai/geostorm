import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"
import type { Competitor } from "@/schemas/project"

export function useCompetitors(projectId: string) {
	return useQuery({
		queryKey: ["competitors", projectId],
		queryFn: () => apiFetch<Competitor[]>(`/projects/${projectId}/competitors`),
		enabled: !!projectId,
	})
}

export function useCreateCompetitor(projectId: string) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (data: {
			name: string
			aliases?: string[]
			website?: string | null
		}) =>
			apiFetch<Competitor>(`/projects/${projectId}/competitors`, {
				method: "POST",
				body: JSON.stringify(data),
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["competitors", projectId],
			})
			queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
		},
	})
}

export function useDeleteCompetitor(projectId: string) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (competitorId: string) =>
			apiFetch<void>(`/projects/${projectId}/competitors/${competitorId}`, {
				method: "DELETE",
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["competitors", projectId],
			})
			queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
		},
	})
}
