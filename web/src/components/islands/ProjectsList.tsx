import { FolderOpen, Plus } from "lucide-react"
import { EmptyState } from "@/components/EmptyState"
import { ProjectCard } from "@/components/ProjectCard"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useProjects } from "@/hooks/useProjects"
import { useApiKeyStatus } from "@/hooks/useSettings"

export function ProjectsList() {
	const { data: projects, isLoading, error } = useProjects()
	const { data: apiKeyStatus } = useApiKeyStatus()
	const hasApiKey = apiKeyStatus?.configured ?? false

	return (
		<div className="space-y-6">
			<div className="flex items-center justify-between">
				<h1 className="text-2xl font-bold tracking-tight">Projects</h1>
				<Button
					asChild
					disabled={!hasApiKey}
					title={
						!hasApiKey ? "Configure your API key in Settings first" : undefined
					}
				>
					<a href={hasApiKey ? "/setup" : "/settings"}>
						<Plus className="mr-2 h-4 w-4" />
						Create Project
					</a>
				</Button>
			</div>

			{isLoading && (
				<div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
					{Array.from({ length: 6 }).map((_, i) => (
						<Skeleton
							key={`skeleton-${i.toString()}`}
							className="h-[120px] rounded-lg"
						/>
					))}
				</div>
			)}

			{error && (
				<div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
					Failed to load projects. Please try again.
				</div>
			)}

			{projects && projects.length === 0 && (
				<EmptyState
					icon={<FolderOpen className="h-12 w-12" />}
					title="No projects yet"
					description="Create your first project to start monitoring your brand's presence in AI responses."
					action={
						<Button asChild>
							<a href="/setup">
								<Plus className="mr-2 h-4 w-4" />
								Create Project
							</a>
						</Button>
					}
				/>
			)}

			{projects && projects.length > 0 && (
				<div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
					{projects.map((project) => (
						<ProjectCard key={project.id} project={project} />
					))}
				</div>
			)}
		</div>
	)
}
