import { useState } from "react"
import { Badge } from "@/components/ui/badge"
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
import { Separator } from "@/components/ui/separator"
import { ApiError, apiFetch } from "@/lib/api"
import { DAY_NAMES } from "@/lib/constants"

function formatHour(hour: number): string {
	if (hour === 0) return "12:00 AM"
	if (hour < 12) return `${hour}:00 AM`
	if (hour === 12) return "12:00 PM"
	return `${hour - 12}:00 PM`
}

function StepIndicator({ current, total }: { current: number; total: number }) {
	return (
		<div className="flex items-center gap-3 mb-6">
			{Array.from({ length: total }, (_, i) => {
				const step = i + 1
				const isCompleted = step < current
				const isCurrent = step === current
				return (
					<div key={step} className="flex items-center gap-2">
						{i > 0 && (
							<div
								className={`h-px w-8 ${
									isCompleted ? "bg-primary" : "bg-border"
								}`}
							/>
						)}
						<div
							className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
								isCurrent
									? "bg-primary text-primary-foreground"
									: isCompleted
										? "bg-primary text-primary-foreground"
										: "border border-border text-muted-foreground"
							}`}
						>
							{step}
						</div>
					</div>
				)
			})}
			<span className="ml-2 text-sm text-muted-foreground">
				Step {current} of {total}
			</span>
		</div>
	)
}

export function SetupWizard() {
	const [step, setStep] = useState(1)

	// Step 1 state
	const [projectName, setProjectName] = useState("")
	const [brandName, setBrandName] = useState("")
	const [brandAliases, setBrandAliases] = useState("")
	const [competitorInput, setCompetitorInput] = useState("")
	const [competitors, setCompetitors] = useState<string[]>([])

	// Step 2 state
	const [termInput, setTermInput] = useState("")
	const [terms, setTerms] = useState<string[]>([])

	// Step 3 state
	const [hour, setHour] = useState(14)
	const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4])

	// Submission state
	const [isSubmitting, setIsSubmitting] = useState(false)
	const [submitError, setSubmitError] = useState<string | null>(null)

	function addCompetitor() {
		const name = competitorInput.trim()
		if (!name || competitors.includes(name)) return
		setCompetitors([...competitors, name])
		setCompetitorInput("")
	}

	function removeCompetitor(name: string) {
		setCompetitors(competitors.filter((c) => c !== name))
	}

	function addTerm() {
		const name = termInput.trim()
		if (!name || terms.includes(name)) return
		setTerms([...terms, name])
		setTermInput("")
	}

	function removeTerm(name: string) {
		setTerms(terms.filter((t) => t !== name))
	}

	function toggleDay(dayIndex: number) {
		setDays((prev) =>
			prev.includes(dayIndex)
				? prev.filter((d) => d !== dayIndex)
				: [...prev, dayIndex].sort(),
		)
	}

	async function handleSubmit() {
		setIsSubmitting(true)
		setSubmitError(null)

		let projectId: string | null = null

		try {
			// 1. Create project
			const aliases = brandAliases
				.split(",")
				.map((a) => a.trim())
				.filter(Boolean)

			const project = await apiFetch<{ id: string }>("/projects", {
				method: "POST",
				body: JSON.stringify({
					name: projectName.trim(),
					brand_name: brandName.trim(),
					brand_aliases: aliases.length > 0 ? aliases : undefined,
					description: null,
				}),
			})

			projectId = project.id

			// 2. Add competitors
			for (const name of competitors) {
				await apiFetch(`/projects/${projectId}/competitors`, {
					method: "POST",
					body: JSON.stringify({ name }),
				})
			}

			// 3. Add terms
			for (const name of terms) {
				await apiFetch(`/projects/${projectId}/terms`, {
					method: "POST",
					body: JSON.stringify({ name }),
				})
			}

			// 4. Set schedule
			await apiFetch(`/projects/${projectId}/schedule`, {
				method: "PATCH",
				body: JSON.stringify({
					hour_of_day: hour,
					days_of_week: days,
				}),
			})

			// 5. Redirect on success
			window.location.href = `/projects/${projectId}`
		} catch (err) {
			// If project was created but a later step failed, redirect anyway
			// so the user can fix the remaining config from the project page
			if (projectId) {
				window.location.href = `/projects/${projectId}`
				return
			}

			if (err instanceof ApiError) {
				const body = err.body as { detail?: string } | undefined
				setSubmitError(body?.detail ?? `API error: ${err.status}`)
			} else if (err instanceof Error) {
				setSubmitError(err.message)
			} else {
				setSubmitError("An unexpected error occurred")
			}
			setIsSubmitting(false)
		}
	}

	return (
		<div>
			<StepIndicator current={step} total={3} />

			{step === 1 && (
				<Card>
					<CardHeader>
						<CardTitle className="text-lg">Project & Brand</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="space-y-2">
							<Label htmlFor="project-name">Project Name *</Label>
							<Input
								id="project-name"
								placeholder="My Brand Monitoring"
								value={projectName}
								onChange={(e) => setProjectName(e.target.value)}
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="brand-name">Brand Name *</Label>
							<Input
								id="brand-name"
								placeholder="Acme Corp"
								value={brandName}
								onChange={(e) => setBrandName(e.target.value)}
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="brand-aliases">
								Brand Aliases (comma-separated, optional)
							</Label>
							<Input
								id="brand-aliases"
								placeholder="Acme, Acme Corporation"
								value={brandAliases}
								onChange={(e) => setBrandAliases(e.target.value)}
							/>
						</div>

						<Separator />

						<div className="space-y-3">
							<Label>Competitors (optional)</Label>
							<div className="flex gap-2">
								<Input
									placeholder="Competitor name"
									value={competitorInput}
									onChange={(e) => setCompetitorInput(e.target.value)}
									onKeyDown={(e) => {
										if (e.key === "Enter") {
											e.preventDefault()
											addCompetitor()
										}
									}}
									className="flex-1"
								/>
								<Button
									type="button"
									variant="outline"
									onClick={addCompetitor}
									disabled={!competitorInput.trim()}
								>
									Add
								</Button>
							</div>
							{competitors.length > 0 && (
								<div className="flex flex-wrap gap-2">
									{competitors.map((name) => (
										<Badge key={name} variant="secondary" className="gap-1">
											{name}
											<button
												type="button"
												onClick={() => removeCompetitor(name)}
												className="ml-1 rounded-full hover:bg-muted-foreground/20"
												aria-label={`Remove ${name}`}
											>
												&times;
											</button>
										</Badge>
									))}
								</div>
							)}
						</div>

						<div className="flex justify-end pt-4">
							<Button
								onClick={() => setStep(2)}
								disabled={!projectName.trim() || !brandName.trim()}
							>
								Next
							</Button>
						</div>
					</CardContent>
				</Card>
			)}

			{step === 2 && (
				<Card>
					<CardHeader>
						<CardTitle className="text-lg">Monitoring Terms</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<p className="text-sm text-muted-foreground">
							Add the search terms you want to monitor. These are the queries
							users ask AI assistants.
						</p>

						<div className="flex gap-2">
							<Input
								placeholder="e.g. best project management tools"
								value={termInput}
								onChange={(e) => setTermInput(e.target.value)}
								onKeyDown={(e) => {
									if (e.key === "Enter") {
										e.preventDefault()
										addTerm()
									}
								}}
								className="flex-1"
							/>
							<Button
								type="button"
								variant="outline"
								onClick={addTerm}
								disabled={!termInput.trim()}
							>
								Add
							</Button>
						</div>

						{terms.length > 0 && (
							<div className="space-y-2">
								{terms.map((name) => (
									<div
										key={name}
										className="flex items-center justify-between rounded-md border px-3 py-2"
									>
										<span className="text-sm">{name}</span>
										<button
											type="button"
											onClick={() => removeTerm(name)}
											className="text-muted-foreground hover:text-foreground"
											aria-label={`Remove ${name}`}
										>
											&times;
										</button>
									</div>
								))}
							</div>
						)}

						{terms.length === 0 && (
							<p className="text-sm text-muted-foreground italic">
								Add at least one monitoring term to continue.
							</p>
						)}

						<div className="flex justify-between pt-4">
							<Button variant="outline" onClick={() => setStep(1)}>
								Back
							</Button>
							<Button onClick={() => setStep(3)} disabled={terms.length === 0}>
								Next
							</Button>
						</div>
					</CardContent>
				</Card>
			)}

			{step === 3 && (
				<Card>
					<CardHeader>
						<CardTitle className="text-lg">Schedule</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="space-y-2">
							<Label>Time of Day</Label>
							<Select
								value={String(hour)}
								onValueChange={(val) => setHour(Number(val))}
							>
								<SelectTrigger>
									<SelectValue placeholder="Select hour" />
								</SelectTrigger>
								<SelectContent>
									{Array.from({ length: 24 }, (_, i) => (
										// biome-ignore lint/suspicious/noArrayIndexKey: static list of 24 hours
										<SelectItem key={`hour-${i}`} value={String(i)}>
											{formatHour(i)}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>

						<div className="space-y-3">
							<Label>Days of Week</Label>
							<div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
								{DAY_NAMES.map((dayName, index) => (
									<div key={dayName} className="flex items-center gap-2">
										<Checkbox
											id={`day-${index}`}
											checked={days.includes(index)}
											onCheckedChange={() => toggleDay(index)}
										/>
										<Label
											htmlFor={`day-${index}`}
											className="text-sm font-normal cursor-pointer"
										>
											{dayName}
										</Label>
									</div>
								))}
							</div>
						</div>

						{submitError && (
							<p className="text-sm text-destructive">{submitError}</p>
						)}

						<div className="flex justify-between pt-4">
							<Button
								variant="outline"
								onClick={() => setStep(2)}
								disabled={isSubmitting}
							>
								Back
							</Button>
							<Button onClick={handleSubmit} disabled={isSubmitting}>
								{isSubmitting ? "Creating Project..." : "Create Project"}
							</Button>
						</div>
					</CardContent>
				</Card>
			)}
		</div>
	)
}
