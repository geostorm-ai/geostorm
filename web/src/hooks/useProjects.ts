import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"
import type {
	CreateProjectRequest,
	Project,
	ProjectDetail,
} from "@/schemas/project"

export function useProjects() {
	return useQuery({
		queryKey: ["projects"],
		queryFn: () => apiFetch<Project[]>("/projects"),
	})
}

export function useProject(projectId: string) {
	return useQuery({
		queryKey: ["projects", projectId],
		queryFn: () => apiFetch<ProjectDetail>(`/projects/${projectId}`),
		enabled: !!projectId,
	})
}

export function useCreateProject() {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (data: CreateProjectRequest) =>
			apiFetch<{ id: string }>("/projects", {
				method: "POST",
				body: JSON.stringify(data),
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["projects"] })
		},
	})
}

export function useUpdateProject(projectId: string) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (data: { name?: string; description?: string | null }) =>
			apiFetch<Project>(`/projects/${projectId}`, {
				method: "PATCH",
				body: JSON.stringify(data),
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["projects"] })
			queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
		},
	})
}

export function useTriggerMonitoring(projectId: string) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: () =>
			apiFetch<{ status: string }>(`/projects/${projectId}/monitor`, {
				method: "POST",
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["runs", projectId] })
		},
	})
}
