import { BrandEditor } from "@/components/islands/BrandEditor"
import { CompetitorsManager } from "@/components/islands/CompetitorsManager"
import { ProvidersManager } from "@/components/islands/ProvidersManager"
import { RunsTable } from "@/components/islands/RunsTable"
import { ScheduleEditor } from "@/components/islands/ScheduleEditor"
import { TermsManager } from "@/components/islands/TermsManager"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useDeleteProject, useProject } from "@/hooks/useProjects"

interface ProjectTabsProps {
	projectId: string
	isDemo: boolean
}

export function ProjectTabs({ projectId, isDemo }: ProjectTabsProps) {
	const { data: project, isLoading } = useProject(projectId)
	const deleteProject = useDeleteProject(projectId)

	function handleDelete() {
		if (window.confirm("Are you sure you want to delete this project? This cannot be undone.")) {
			deleteProject.mutate()
		}
	}

	return (
		<Tabs defaultValue="overview" className="space-y-4">
			<TabsList>
				<TabsTrigger value="overview">Overview</TabsTrigger>
				<TabsTrigger value="terms">Terms</TabsTrigger>
				<TabsTrigger value="schedule">Schedule</TabsTrigger>
				<TabsTrigger value="competitors">Competitors</TabsTrigger>
				<TabsTrigger value="runs">Runs</TabsTrigger>
				<TabsTrigger value="providers">Providers</TabsTrigger>
			</TabsList>

			<TabsContent value="overview">
				{isLoading ? (
					<Card>
						<CardHeader>
							<Skeleton className="h-6 w-48" />
						</CardHeader>
						<CardContent className="space-y-3">
							<Skeleton className="h-4 w-full" />
							<Skeleton className="h-4 w-3/4" />
							<Skeleton className="h-4 w-1/2" />
						</CardContent>
					</Card>
				) : project ? (
					<div className="space-y-6">
						<Card>
							<CardHeader>
								<CardTitle>Project Overview</CardTitle>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="grid gap-4 sm:grid-cols-2">
									<div>
										<p className="text-sm font-medium text-muted-foreground">
											Brand Name
										</p>
										<p className="text-sm">
											{project.brand?.name ?? "Not set"}
										</p>
									</div>
									<div>
										<p className="text-sm font-medium text-muted-foreground">
											Aliases
										</p>
										<p className="text-sm">
											{project.brand?.aliases.length
												? project.brand.aliases.join(", ")
												: "None"}
										</p>
									</div>
									<div>
										<p className="text-sm font-medium text-muted-foreground">
											Description
										</p>
										<p className="text-sm">
											{project.description ?? "No description"}
										</p>
									</div>
									<div>
										<p className="text-sm font-medium text-muted-foreground">
											Competitors
										</p>
										<p className="text-sm">
											{project.competitors.length} configured
										</p>
									</div>
									<div>
										<p className="text-sm font-medium text-muted-foreground">
											Search Terms
										</p>
										<p className="text-sm">{project.terms.length} configured</p>
									</div>
								</div>
							</CardContent>
						</Card>
						<BrandEditor projectId={projectId} isDemo={isDemo} />
						{!isDemo && (
							<Card className="border-destructive/50">
								<CardHeader>
									<CardTitle className="text-destructive">Danger Zone</CardTitle>
								</CardHeader>
								<CardContent className="flex items-center justify-between">
									<p className="text-sm text-muted-foreground">
										Permanently delete this project and all its data.
									</p>
									<Button
										variant="destructive"
										onClick={handleDelete}
										disabled={deleteProject.isPending}
									>
										{deleteProject.isPending ? "Deleting..." : "Delete Project"}
									</Button>
								</CardContent>
							</Card>
						)}
					</div>
				) : null}
			</TabsContent>

			<TabsContent value="terms">
				<TermsManager projectId={projectId} isDemo={isDemo} />
			</TabsContent>

			<TabsContent value="schedule">
				<ScheduleEditor projectId={projectId} isDemo={isDemo} />
			</TabsContent>

			<TabsContent value="competitors">
				<CompetitorsManager projectId={projectId} isDemo={isDemo} />
			</TabsContent>

			<TabsContent value="runs">
				<RunsTable projectId={projectId} isDemo={isDemo} />
			</TabsContent>

			<TabsContent value="providers">
				<ProvidersManager projectId={projectId} isDemo={isDemo} />
			</TabsContent>
		</Tabs>
	)
}
