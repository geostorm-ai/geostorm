import { Badge } from "@/components/ui/badge"
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card"
import type { Project } from "@/schemas/project"

interface ProjectCardProps {
	project: Project
}

export function ProjectCard({ project }: ProjectCardProps) {
	return (
		<a href={`/projects/${project.id}`} className="block">
			<Card className="transition-colors hover:bg-accent/50">
				<CardHeader>
					<div className="flex items-center justify-between">
						<CardTitle className="text-lg">{project.name}</CardTitle>
						{project.is_demo && (
							<Badge
								variant="secondary"
								className="bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
							>
								Demo
							</Badge>
						)}
					</div>
					{project.description && (
						<CardDescription>{project.description}</CardDescription>
					)}
					<CardDescription className="text-xs">
						Created {new Date(project.created_at).toLocaleDateString()}
					</CardDescription>
				</CardHeader>
				<CardContent>
					<div className="flex items-center gap-4 text-sm text-muted-foreground">
						{project.latest_score != null && (
							<span title="Perception Score">
								Score: <span className="font-medium text-foreground">{project.latest_score.toFixed(1)}</span>
							</span>
						)}
						{project.run_count != null && project.run_count > 0 && (
							<span>
								{project.run_count} {project.run_count === 1 ? "run" : "runs"}
							</span>
						)}
						{project.active_alert_count != null && project.active_alert_count > 0 && (
							<Badge
								variant="secondary"
								className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
							>
								{project.active_alert_count} {project.active_alert_count === 1 ? "alert" : "alerts"}
							</Badge>
						)}
					</div>
				</CardContent>
			</Card>
		</a>
	)
}
