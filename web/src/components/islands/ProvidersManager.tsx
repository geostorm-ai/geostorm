import { AlertCircle, X } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
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

interface ProvidersManagerProps {
	projectId: string
	isDemo: boolean
}

export function ProvidersManager({ projectId, isDemo }: ProvidersManagerProps) {
	const { data: providers, isLoading } = useProviders(projectId)
	const createProvider = useCreateProvider(projectId)
	const updateProvider = useUpdateProvider(projectId)
	const deleteProvider = useDeleteProvider(projectId)
	const [providerName, setProviderName] = useState("openrouter")
	const [modelName, setModelName] = useState("")

	function handleSubmit(e: React.FormEvent) {
		e.preventDefault()
		const trimmed = modelName.trim()
		if (!trimmed) return
		createProvider.mutate(
			{ provider_name: providerName, model_name: trimmed },
			{ onSuccess: () => setModelName("") },
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

				<form onSubmit={handleSubmit} className="space-y-3">
					<div className="flex gap-2">
						<div className="w-40">
							<Label htmlFor="provider-name" className="sr-only">Provider</Label>
							<Select
								value={providerName}
								onValueChange={setProviderName}
								disabled={isDemo}
							>
								<SelectTrigger id="provider-name">
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="openrouter">OpenRouter</SelectItem>
								</SelectContent>
							</Select>
						</div>
						<Input
							placeholder="Model name (e.g. openai/gpt-4o)"
							value={modelName}
							onChange={(e) => setModelName(e.target.value)}
							disabled={isDemo || createProvider.isPending}
							className="flex-1"
						/>
						<Button
							type="submit"
							disabled={isDemo || createProvider.isPending || !modelName.trim()}
						>
							Add
						</Button>
					</div>
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
