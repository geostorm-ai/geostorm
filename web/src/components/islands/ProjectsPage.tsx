import { QueryProvider } from "@/components/providers/QueryProvider"
import { ProjectsList } from "./ProjectsList"

export function ProjectsPage() {
	return (
		<div className="p-6">
			<QueryProvider>
				<ProjectsList />
			</QueryProvider>
		</div>
	)
}
