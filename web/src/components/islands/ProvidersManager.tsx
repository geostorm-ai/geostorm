import { AlertCircle, X } from "lucide-react"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
	useProviders,
	useCreateProvider,
	useUpdateProvider,
	useDeleteProvider,
} from "@/hooks/useProviders"

interface RecommendedModel {
	id: string
	name: string
}

function useRecommendedModels() {
	return useQuery<RecommendedModel[]>({
		queryKey: ["recommended-models"],
		queryFn: async () => {
			const res = await fetch("/api/settings/models")
			if (!res.ok) throw new Error("Failed to fetch models")
			return res.json()
		},
	})
}

interface ProvidersManagerProps {
	projectId: string
	isDemo: boolean
}

export function ProvidersManager({ projectId, isDemo }: ProvidersManagerProps) {
	const { data: providers, isLoading } = useProviders(projectId)
	const { data: recommendedModels } = useRecommendedModels()
	const createProvider = useCreateProvider(projectId)
	const updateProvider = useUpdateProvider(projectId)
	const deleteProvider = useDeleteProvider(projectId)
	const [selectedModel, setSelectedModel] = useState("")

	function handleSubmit(e: React.FormEvent) {
		e.preventDefault()
		if (!selectedModel) return
		createProvider.mutate(
			{ provider_name: "openrouter", model_name: selectedModel },
			{ onSuccess: () => setSelectedModel("") },
		)
	}

	if (isLoading) {
		return (
			<Card>
				<CardHeader>
					<CardTitle>LLM Providers</CardTitle>
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
				<CardTitle>LLM Providers</CardTitle>
			</CardHeader>
			<CardContent className="space-y-4">
				{isDemo && (
					<div className="flex items-center gap-2 rounded-md bg-blue-50 p-3 text-sm text-blue-700 dark:bg-blue-950 dark:text-blue-300">
						<AlertCircle className="h-4 w-4 shrink-0" />
						Read-only demo project
					</div>
				)}

				<form onSubmit={handleSubmit} className="flex gap-2">
					<div className="flex-1">
						<Label htmlFor="model-select" className="sr-only">Model</Label>
						<Select
							value={selectedModel}
							onValueChange={setSelectedModel}
							disabled={isDemo}
						>
							<SelectTrigger id="model-select">
								<SelectValue placeholder="Select a model..." />
							</SelectTrigger>
							<SelectContent>
								{recommendedModels?.map((m) => (
									<SelectItem key={m.id} value={m.id}>
										{m.name}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</div>
					<Button
						type="submit"
						disabled={isDemo || createProvider.isPending || !selectedModel}
					>
						Add
					</Button>
				</form>

				{providers && providers.length === 0 && (
					<p className="py-4 text-center text-sm text-muted-foreground">
						No providers configured. Add one above.
					</p>
				)}

				{providers && providers.length > 0 && (
					<ul className="space-y-2">
						{providers.map((provider) => (
							<li
								key={provider.id}
								className="flex items-center justify-between rounded-md border px-3 py-2"
							>
								<div className="flex items-center gap-3">
									<Checkbox
										checked={provider.is_enabled}
										onCheckedChange={(checked) =>
											updateProvider.mutate({
												providerId: provider.id,
												is_enabled: !!checked,
											})
										}
										disabled={isDemo || updateProvider.isPending}
									/>
									<div>
										<span className="text-sm font-medium">
											{provider.model_name}
										</span>
										<span className="ml-2 text-xs text-muted-foreground">
											({provider.provider_name})
										</span>
									</div>
								</div>
								<Button
									variant="ghost"
									size="icon"
									className="h-7 w-7"
									onClick={() => {
									if (window.confirm(`Remove ${provider.model_name}?`)) {
										deleteProvider.mutate(provider.id)
									}
								}}
									disabled={isDemo || deleteProvider.isPending}
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
