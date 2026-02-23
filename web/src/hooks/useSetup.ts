import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api"
import type { SetupStatus } from "@/schemas/setup"

export function useSetupStatus() {
	return useQuery({
		queryKey: ["setup", "status"],
		queryFn: () => apiFetch<SetupStatus>("/setup/status"),
	})
}
