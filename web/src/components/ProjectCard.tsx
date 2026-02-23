import { Badge } from "@/components/ui/badge"
import {
	Card,
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
			</Card>
		</a>
	)
}
