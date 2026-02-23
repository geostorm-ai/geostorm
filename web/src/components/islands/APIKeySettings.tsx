import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
	useApiKeyStatus,
	useDeleteApiKey,
	useSaveApiKey,
} from "@/hooks/useSettings"

export function APIKeySettings() {
	const { data: status, isLoading, error: fetchError } = useApiKeyStatus()
	const saveMutation = useSaveApiKey()
	const deleteMutation = useDeleteApiKey()

	const [apiKey, setApiKey] = useState("")
	const [confirmDelete, setConfirmDelete] = useState(false)

	function handleSave() {
		if (!apiKey.trim()) return
		saveMutation.mutate(apiKey.trim(), {
			onSuccess: () => {
				setApiKey("")
			},
		})
	}

	function handleDelete() {
		if (!confirmDelete) {
			setConfirmDelete(true)
			return
		}
		deleteMutation.mutate(undefined, {
			onSuccess: () => {
				setConfirmDelete(false)
			},
		})
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle className="text-lg">API Key</CardTitle>
				<CardDescription>
					Configure your API key to enable AI monitoring. The key is used to
					query AI models for brand perception data.
				</CardDescription>
			</CardHeader>
			<CardContent className="space-y-6">
				{/* Status indicator */}
				<div className="flex items-center gap-3">
					<span className="text-sm font-medium">Status:</span>
					{isLoading ? (
						<span className="text-sm text-muted-foreground">Loading...</span>
					) : fetchError ? (
						<span className="text-sm text-destructive">
							Failed to load status
						</span>
					) : status?.configured ? (
						<div className="flex items-center gap-2">
							<span className="inline-block h-2.5 w-2.5 rounded-full bg-green-500" />
							<Badge variant="secondary">
								Configured (from {status.source})
							</Badge>
						</div>
					) : (
						<div className="flex items-center gap-2">
							<span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" />
							<Badge variant="outline">Not configured</Badge>
						</div>
					)}
				</div>

				<Separator />

				{/* Save key form */}
				<div className="space-y-3">
					<Label htmlFor="api-key">
						{status?.configured ? "Replace API Key" : "Enter API Key"}
					</Label>
					<div className="flex gap-2">
						<Input
							id="api-key"
							type="password"
							placeholder="sk-or-v1-..."
							value={apiKey}
							onChange={(e) => {
								setApiKey(e.target.value)
								saveMutation.reset()
							}}
							className="flex-1"
						/>
						<Button
							onClick={handleSave}
							disabled={!apiKey.trim() || saveMutation.isPending}
						>
							{saveMutation.isPending ? "Saving..." : "Save API Key"}
						</Button>
					</div>

					{saveMutation.isSuccess && (
						<p className="text-sm text-green-600 dark:text-green-400">
							API key saved successfully. You can now create projects.
						</p>
					)}

					{saveMutation.isError && (
						<p className="text-sm text-destructive">
							{saveMutation.error instanceof Error
								? saveMutation.error.message
								: "Failed to save API key"}
						</p>
					)}
				</div>

				{/* Delete key */}
				{status?.configured && status.source === "database" && (
					<>
						<Separator />
						<div className="space-y-3">
							<Label>Delete API Key</Label>
							<p className="text-sm text-muted-foreground">
								Remove the stored API key from the database. This will disable
								AI monitoring until a new key is configured.
							</p>
							<div className="flex items-center gap-2">
								<Button
									variant="destructive"
									onClick={handleDelete}
									disabled={deleteMutation.isPending}
								>
									{deleteMutation.isPending
										? "Deleting..."
										: confirmDelete
											? "Click again to confirm"
											: "Delete API Key"}
								</Button>
								{confirmDelete && (
									<Button
										variant="ghost"
										size="sm"
										onClick={() => setConfirmDelete(false)}
									>
										Cancel
									</Button>
								)}
							</div>

							{deleteMutation.isError && (
								<p className="text-sm text-destructive">
									{deleteMutation.error instanceof Error
										? deleteMutation.error.message
										: "Failed to delete API key"}
								</p>
							)}
						</div>
					</>
				)}
			</CardContent>
		</Card>
	)
}
