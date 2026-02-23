import { AlertCircle, Check } from "lucide-react"
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { useBrand, useUpdateBrand } from "@/hooks/useBrand"

interface BrandEditorProps {
	projectId: string
	isDemo: boolean
}

export function BrandEditor({ projectId, isDemo }: BrandEditorProps) {
	const { data: brand, isLoading } = useBrand(projectId)
	const updateBrand = useUpdateBrand(projectId)
	const [name, setName] = useState("")
	const [aliasesText, setAliasesText] = useState("")
	const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">(
		"idle",
	)

	useEffect(() => {
		if (brand) {
			setName(brand.name)
			setAliasesText(brand.aliases.join(", "))
		}
	}, [brand])

	function handleSave() {
		setSaveStatus("idle")
		const aliases = aliasesText
			.split(",")
			.map((a) => a.trim())
			.filter(Boolean)
		updateBrand.mutate(
			{ name, aliases },
			{
				onSuccess: () => {
					setSaveStatus("success")
					setTimeout(() => setSaveStatus("idle"), 3000)
				},
				onError: () => {
					setSaveStatus("error")
					setTimeout(() => setSaveStatus("idle"), 3000)
				},
			},
		)
	}

	if (isLoading) {
		return (
			<Card>
				<CardHeader>
					<CardTitle>Brand</CardTitle>
				</CardHeader>
				<CardContent className="space-y-4">
					<Skeleton className="h-10 w-full" />
					<Skeleton className="h-10 w-full" />
				</CardContent>
			</Card>
		)
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle>Brand</CardTitle>
			</CardHeader>
			<CardContent className="space-y-4">
				{isDemo && (
					<div className="flex items-center gap-2 rounded-md bg-blue-50 p-3 text-sm text-blue-700 dark:bg-blue-950 dark:text-blue-300">
						<AlertCircle className="h-4 w-4 shrink-0" />
						Read-only demo project
					</div>
				)}

				<div className="space-y-2">
					<Label htmlFor="brand-name">Brand Name</Label>
					<Input
						id="brand-name"
						value={name}
						onChange={(e) => setName(e.target.value)}
						disabled={isDemo || updateBrand.isPending}
					/>
				</div>

				<div className="space-y-2">
					<Label htmlFor="brand-aliases">Aliases (comma-separated)</Label>
					<Input
						id="brand-aliases"
						placeholder="e.g. Acme Corp, Acme Inc"
						value={aliasesText}
						onChange={(e) => setAliasesText(e.target.value)}
						disabled={isDemo || updateBrand.isPending}
					/>
				</div>

				<div className="flex items-center gap-3">
					<Button
						onClick={handleSave}
						disabled={isDemo || updateBrand.isPending || !name.trim()}
					>
						{updateBrand.isPending ? "Saving..." : "Save"}
					</Button>
					{saveStatus === "success" && (
						<span className="flex items-center gap-1 text-sm text-green-600 dark:text-green-400">
							<Check className="h-4 w-4" />
							Brand saved
						</span>
					)}
					{saveStatus === "error" && (
						<span className="text-sm text-destructive">
							Failed to save brand
						</span>
					)}
				</div>
			</CardContent>
		</Card>
	)
}
