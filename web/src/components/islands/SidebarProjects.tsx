import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { apiFetch } from "@/lib/api"
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip"
import type { Project } from "@/schemas/project"

interface SidebarProjectsProps {
	currentPath: string
}

export function SidebarProjects({ currentPath }: SidebarProjectsProps) {
	const [queryClient] = useState(
		() => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } }),
	)

	return (
		<QueryClientProvider client={queryClient}>
			<SidebarProjectsInner currentPath={currentPath} />
		</QueryClientProvider>
	)
}

function SidebarProjectsInner({ currentPath }: SidebarProjectsProps) {
	const { data: projects, isLoading } = useQuery({
		queryKey: ["projects"],
		queryFn: () => apiFetch<Project[]>("/projects"),
	})

	if (isLoading || !projects) {
		return (
			<p className="px-2 py-4 text-center text-sm text-muted-foreground">
				Loading...
			</p>
		)
	}

	if (projects.length === 0) {
		return (
			<p className="px-2 py-4 text-center text-sm text-muted-foreground">
				No projects yet
			</p>
		)
	}

	return (
		<TooltipProvider delayDuration={300}>
			{projects.map((project) => {
				const href = `/projects/${project.id}`
				const isActive = currentPath === href
				return (
					<Tooltip key={project.id}>
						<TooltipTrigger asChild>
							<a
								href={href}
								className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors ${
									isActive
										? "bg-accent text-accent-foreground"
										: "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
								}`}
							>
								<span className="truncate flex-1">{project.name}</span>
								{project.is_demo && (
									<span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900 dark:text-blue-300">
										Demo
									</span>
								)}
							</a>
						</TooltipTrigger>
						<TooltipContent side="right">{project.name}</TooltipContent>
					</Tooltip>
				)
			})}
		</TooltipProvider>
	)
}
