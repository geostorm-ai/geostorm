import { AlertCircle, X } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
	useCompetitors,
	useCreateCompetitor,
	useDeleteCompetitor,
} from "@/hooks/useCompetitors"

interface CompetitorsManagerProps {
	projectId: string
	isDemo: boolean
}

export function CompetitorsManager({
	projectId,
	isDemo,
}: CompetitorsManagerProps) {
	const { data: competitors, isLoading } = useCompetitors(projectId)
	const createCompetitor = useCreateCompetitor(projectId)
	const deleteCompetitor = useDeleteCompetitor(projectId)
	const [newName, setNewName] = useState("")

	function handleSubmit(e: React.FormEvent) {
		e.preventDefault()
		const trimmed = newName.trim()
		if (!trimmed) return
		createCompetitor.mutate(
			{ name: trimmed },
			{
				onSuccess: () => setNewName(""),
			},
		)
	}

	if (isLoading) {
		return (
			<Card>
				<CardHeader>
					<CardTitle>Competitors</CardTitle>
				</CardHeader>
				<CardContent className="space-y-3">
					<Skeleton className="h-10 w-full" />
					<Skeleton className="h-8 w-3/4" />
					<Skeleton className="h-8 w-1/2" />
				</CardContent>
			</Card>
		)
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle>Competitors</CardTitle>
			</CardHeader>
			<CardContent className="space-y-4">
				{isDemo && (
					<div className="flex items-center gap-2 rounded-md bg-blue-50 p-3 text-sm text-blue-700 dark:bg-blue-950 dark:text-blue-300">
						<AlertCircle className="h-4 w-4 shrink-0" />
						Read-only demo project
					</div>
				)}

				<form onSubmit={handleSubmit} className="flex gap-2">
					<Input
						placeholder="Add a competitor..."
						value={newName}
						onChange={(e) => setNewName(e.target.value)}
						disabled={isDemo || createCompetitor.isPending}
					/>
					<Button
						type="submit"
						disabled={isDemo || createCompetitor.isPending || !newName.trim()}
					>
						Add
					</Button>
				</form>

				{competitors && competitors.length === 0 && (
					<p className="py-4 text-center text-sm text-muted-foreground">
						No competitors yet. Add one above.
					</p>
				)}

				{competitors && competitors.length > 0 && (
					<ul className="space-y-2">
						{competitors.map((competitor) => (
							<li
								key={competitor.id}
								className="flex items-center justify-between rounded-md border px-3 py-2"
							>
								<span className="text-sm">{competitor.name}</span>
								<Button
									variant="ghost"
									size="icon"
									className="h-7 w-7"
									onClick={() => deleteCompetitor.mutate(competitor.id)}
									disabled={isDemo || deleteCompetitor.isPending}
								>
									<X className="h-4 w-4" />
								</Button>
							</li>
						))}
					</ul>
				)}
			</CardContent>
		</Card>
	)
}
