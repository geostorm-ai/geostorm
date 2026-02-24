import { QueryProvider } from "@/components/providers/QueryProvider"
import { SetupWizard } from "./SetupWizard"

export function SetupPage() {
	return (
		<div className="min-h-screen flex flex-col">
			<header className="border-b px-6 py-4">
				<div className="flex items-center gap-4">
					<a href="/projects" className="text-sm text-muted-foreground hover:text-foreground">&larr; Back to projects</a>
					<span className="text-sm font-semibold">Create New Project</span>
				</div>
			</header>
			<div className="flex-1 flex items-start justify-center p-6">
				<div className="w-full max-w-xl">
					<QueryProvider>
						<SetupWizard />
					</QueryProvider>
				</div>
			</div>
		</div>
	)
}
