import { AlertCircle, X } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useCreateTerm, useDeleteTerm, useTerms } from "@/hooks/useTerms"

interface TermsManagerProps {
	projectId: string
	isDemo: boolean
}

export function TermsManager({ projectId, isDemo }: TermsManagerProps) {
	const { data: terms, isLoading } = useTerms(projectId)
	const createTerm = useCreateTerm(projectId)
	const deleteTerm = useDeleteTerm(projectId)
	const [newTermName, setNewTermName] = useState("")

	function handleSubmit(e: React.FormEvent) {
		e.preventDefault()
		const trimmed = newTermName.trim()
		if (!trimmed) return
		createTerm.mutate(
			{ name: trimmed },
			{
				onSuccess: () => setNewTermName(""),
			},
		)
	}

	if (isLoading) {
		return (
			<Card>
				<CardHeader>
					<CardTitle>Search Terms</CardTitle>
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
				<CardTitle>Search Terms</CardTitle>
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
						placeholder="Add a search term..."
						value={newTermName}
						onChange={(e) => setNewTermName(e.target.value)}
						disabled={isDemo || createTerm.isPending}
					/>
					<Button
						type="submit"
						disabled={isDemo || createTerm.isPending || !newTermName.trim()}
					>
						Add
					</Button>
				</form>

				{terms && terms.length === 0 && (
					<p className="py-4 text-center text-sm text-muted-foreground">
						No search terms yet. Add one above.
					</p>
				)}

				{terms && terms.length > 0 && (
					<ul className="space-y-2">
						{terms.map((term) => (
							<li
								key={term.id}
								className="flex items-center justify-between rounded-md border px-3 py-2"
							>
								<span className="text-sm">{term.name}</span>
								<Button
									variant="ghost"
									size="icon"
									className="h-7 w-7"
									onClick={() => deleteTerm.mutate(term.id)}
									disabled={isDemo || deleteTerm.isPending}
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
