import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import type { Project } from "@/schemas/project"

export function HomeRedirect() {
	const [queryClient] = useState(
		() => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } }),
	)

	return (
		<QueryClientProvider client={queryClient}>
			<HomeRedirectInner />
		</QueryClientProvider>
	)
}

function HomeRedirectInner() {
	const { data: projects } = useQuery({
		queryKey: ["projects"],
		queryFn: () => apiFetch<Project[]>("/projects"),
	})

	useEffect(() => {
		if (!projects) return
		if (projects.length > 0) {
			const demo = projects.find((p) => p.is_demo)
			window.location.href = `/projects/${(demo ?? projects[0]).id}`
		} else {
			window.location.href = "/projects"
		}
	}, [projects])

	return (
		<div className="flex min-h-screen items-center justify-center">
			<p className="text-muted-foreground">Loading...</p>
		</div>
	)
}
