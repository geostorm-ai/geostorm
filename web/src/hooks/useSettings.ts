import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"
import type { ApiKeyStatus } from "@/schemas/setup"

export function useApiKeyStatus() {
	return useQuery({
		queryKey: ["settings", "api-key-status"],
		queryFn: () => apiFetch<ApiKeyStatus>("/settings/api-key-status"),
	})
}

export function useSaveApiKey() {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (key: string) =>
			apiFetch<{ status: string }>("/settings/api-key", {
				method: "POST",
				body: JSON.stringify({ key }),
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["settings"] })
			queryClient.invalidateQueries({ queryKey: ["setup"] })
		},
	})
}

export function useDeleteApiKey() {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: () => apiFetch<void>("/settings/api-key", { method: "DELETE" }),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["settings"] })
			queryClient.invalidateQueries({ queryKey: ["setup"] })
		},
	})
}
