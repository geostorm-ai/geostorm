import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { AlertsFeed } from "./AlertsFeed"
import { MonitorButton } from "./MonitorButton"
import { PerceptionChart } from "./PerceptionChart"
import { ProjectTabs } from "./ProjectTabs"
import { SignalPanel } from "./SignalPanel"
import { apiFetch } from "@/lib/api"
import { useRuns } from "@/hooks/useRuns"
import { useApiKeyStatus } from "@/hooks/useSettings"
import type { ProjectDetail } from "@/schemas/project"

function ApiKeyBanner() {
	const { data: apiKeyStatus, isLoading } = useApiKeyStatus()

	if (isLoading || apiKeyStatus?.configured !== false) return null

	return (
		<div className="border-b bg-amber-50 px-4 py-3 dark:bg-amber-950/50">
			<div className="flex items-center gap-3">
				<div className="flex-1">
					<p className="text-sm font-medium text-amber-900 dark:text-amber-100">
						No API key configured. Monitoring runs cannot start.{" "}
						<a
							href="/settings"
							className="ml-1 underline underline-offset-4 hover:text-amber-700 dark:hover:text-amber-300"
						>
							Add your OpenRouter API key in Settings
						</a>{" "}
						to begin monitoring.
					</p>
				</div>
			</div>
		</div>
	)
}

function DemoBanner() {
	const { data: setupStatus } = useQuery({
		queryKey: ["setup-status"],
		queryFn: () => apiFetch<{ has_api_key: boolean; has_projects: boolean }>("/setup/status"),
	})

	const hasApiKey = setupStatus?.has_api_key ?? false

	return (
		<div className="border-b bg-blue-50 px-4 py-3 dark:bg-blue-950/50">
			<div className="flex items-center gap-3">
				<div className="flex-1">
					<p className="text-sm font-medium text-blue-900 dark:text-blue-100">
						You're viewing a read-only demo project.{" "}
						{hasApiKey ? (
							<a
								href="/projects"
								className="ml-1 underline underline-offset-4 hover:text-blue-700 dark:hover:text-blue-300"
							>
								Go to your projects
							</a>
						) : (
							<a
								href="/settings"
								className="ml-1 underline underline-offset-4 hover:text-blue-700 dark:hover:text-blue-300"
							>
								Add your OpenRouter API key
							</a>
						)}{" "}
						to start monitoring your own software.
					</p>
				</div>
			</div>
		</div>
	)
}

export function ProjectDetailPage() {
	const [queryClient] = useState(
		() => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } }),
	)

	return (
		<QueryClientProvider client={queryClient}>
			<ProjectDetailPageInner />
		</QueryClientProvider>
	)
}

function ProjectDetailPageInner() {
	const id = typeof window !== "undefined"
		? window.location.pathname.split("/projects/")[1]?.split("/")[0]
		: undefined

	const { data: project, isLoading, error } = useQuery({
		queryKey: ["project", id],
		queryFn: () => apiFetch<ProjectDetail>(`/projects/${id}`),
		enabled: !!id,
	})

	const { data: runsData } = useRuns(id ?? "", { limit: 1, enablePolling: !!id && !isLoading && !error })
	const runCount = runsData?.total

	if (!id) {
		return (
			<div className="p-6 text-center text-muted-foreground">
				Project not found.
			</div>
		)
	}

	if (isLoading) {
		return (
			<div className="p-6 text-center text-muted-foreground">
				Loading project...
			</div>
		)
	}

	if (error || !project) {
		return (
			<div className="p-6 text-center text-muted-foreground">
				Project not found.
			</div>
		)
	}

	return (
		<>
			{project.is_demo && <DemoBanner />}
			{!project.is_demo && <ApiKeyBanner />}
			<div className="space-y-6 p-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold tracking-tight">
							{project.name}
						</h1>
						{project.description && (
							<p className="text-sm text-muted-foreground">
								{project.description}
							</p>
						)}
					</div>
					<MonitorButton projectId={id} isDemo={project.is_demo} />
				</div>

				<AlertsFeed projectId={id} runCount={runCount} />
				<div className="mt-6">
					<SignalPanel projectId={id} />
				</div>
				<div className="mt-6">
					<ProjectTabs projectId={id} isDemo={project.is_demo} />
				</div>
				<PerceptionChart projectId={id} runCount={runCount} />
			</div>
		</>
	)
}
