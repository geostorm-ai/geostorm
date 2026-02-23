import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"
import type { Schedule } from "@/schemas/project"

export function useSchedule(projectId: string) {
	return useQuery({
		queryKey: ["schedule", projectId],
		queryFn: () => apiFetch<Schedule>(`/projects/${projectId}/schedule`),
		enabled: !!projectId,
	})
}

export function useUpdateSchedule(projectId: string) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (data: {
			hour_of_day?: number
			days_of_week?: number[]
			is_active?: boolean
		}) =>
			apiFetch<Schedule>(`/projects/${projectId}/schedule`, {
				method: "PATCH",
				body: JSON.stringify(data),
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["schedule", projectId] })
			queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
		},
	})
}
