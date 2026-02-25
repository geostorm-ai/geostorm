import { useState } from "react"
import { Alert, AlertDescription } from "@/components/ui/alert"
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
import { Textarea } from "@/components/ui/textarea"
import { ApiError, apiFetch } from "@/lib/api"
import { DAY_NAMES } from "@/lib/constants"
import { useApiKeyStatus, useSaveApiKey } from "@/hooks/useSettings"

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
							{isCompleted ? (
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
									<polyline points="20 6 9 17 4 12" />
								</svg>
							) : (
								step
							)}
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

interface AutofillData {
	brand_name: string
	brand_aliases: string[]
	description: string
	competitors: string[]
	monitoring_terms: string[]
}

export function SetupWizard() {
	const [step, setStep] = useState(1)

	// Primary input (only required field)
	const [primaryInput, setPrimaryInput] = useState("")

	// Optional fields
	const [projectName, setProjectName] = useState("")
	const [description, setDescription] = useState("")
	const [brandName, setBrandName] = useState("")
	const [brandAliases, setBrandAliases] = useState("")
	const [competitorInput, setCompetitorInput] = useState("")
	const [competitors, setCompetitors] = useState<string[]>([])
	const [termInput, setTermInput] = useState("")
	const [terms, setTerms] = useState<string[]>([])
	const [hour, setHour] = useState(14)
	const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4])

	// AI autofill state
	const [isAutofilling, setIsAutofilling] = useState(false)
	const [autofillError, setAutofillError] = useState<string | null>(null)
	const [showApiKeyInput, setShowApiKeyInput] = useState(false)
	const [inlineApiKey, setInlineApiKey] = useState("")

	// Submission state
	const [isSubmitting, setIsSubmitting] = useState(false)
	const [submitError, setSubmitError] = useState<string | null>(null)
	const [createdProjectId, setCreatedProjectId] = useState<string | null>(null)
	const [monitorTriggered, setMonitorTriggered] = useState(false)

	// API key hooks
	const { data: apiKeyStatus } = useApiKeyStatus()
	const saveApiKey = useSaveApiKey()

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

	function applyAutofillData(data: AutofillData) {
		if (data.brand_name) setBrandName(data.brand_name)
		if (data.brand_aliases?.length) setBrandAliases(data.brand_aliases.join(", "))
		if (data.description) setDescription(data.description)
		if (data.competitors?.length) setCompetitors(data.competitors)
		if (data.monitoring_terms?.length) setTerms(data.monitoring_terms)
	}

	async function handleAutofill() {
		if (!primaryInput.trim()) return

		// Check if API key is configured
		if (!apiKeyStatus?.configured) {
			setShowApiKeyInput(true)
			return
		}

		setIsAutofilling(true)
		setAutofillError(null)

		try {
			const data = await apiFetch<AutofillData>("/setup/autofill", {
				method: "POST",
				body: JSON.stringify({ input: primaryInput.trim() }),
			})
			applyAutofillData(data)
		} catch (err) {
			if (err instanceof ApiError) {
				if (err.status === 400) {
					setShowApiKeyInput(true)
					setAutofillError(null)
				} else {
					const body = err.body as { detail?: string } | undefined
					setAutofillError(body?.detail ?? "AI autofill failed. You can fill in the fields manually.")
				}
			} else {
				setAutofillError("AI autofill failed. You can fill in the fields manually.")
			}
		} finally {
			setIsAutofilling(false)
		}
	}

	async function handleSaveKeyAndAutofill() {
		if (!inlineApiKey.trim()) return

		try {
			await saveApiKey.mutateAsync(inlineApiKey.trim())
			setShowApiKeyInput(false)
			setInlineApiKey("")
			// Now trigger autofill with the newly saved key
			setIsAutofilling(true)
			setAutofillError(null)
			try {
				const data = await apiFetch<AutofillData>("/setup/autofill", {
					method: "POST",
					body: JSON.stringify({ input: primaryInput.trim() }),
				})
				applyAutofillData(data)
			} catch (err) {
				if (err instanceof ApiError) {
					const body = err.body as { detail?: string } | undefined
					setAutofillError(body?.detail ?? "AI autofill failed. You can fill in the fields manually.")
				} else {
					setAutofillError("AI autofill failed. You can fill in the fields manually.")
				}
			} finally {
				setIsAutofilling(false)
			}
		} catch {
			setAutofillError("Failed to save API key.")
		}
	}

	async function handleSubmit() {
		setIsSubmitting(true)
		setSubmitError(null)

		const effectiveProjectName = projectName.trim() || primaryInput.trim()
		const effectiveBrandName = brandName.trim() || primaryInput.trim()

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
					name: effectiveProjectName,
					brand_name: effectiveBrandName,
					brand_aliases: aliases.length > 0 ? aliases : undefined,
					description: description.trim() || null,
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

			// 5. Auto-trigger first monitoring run
			apiFetch(`/projects/${projectId}/monitor`, { method: "POST" })
				.then(() => setMonitorTriggered(true))
				.catch(() => {
					// Non-blocking — if it fails, user can trigger manually
				})

			// 6. Show confirmation step
			setCreatedProjectId(projectId)
			setStep(2)
			setIsSubmitting(false)
		} catch (err) {
			// If project was created but a later step failed, redirect anyway
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
			<StepIndicator current={step} total={2} />

			{step === 1 && (
				<Card>
					<CardHeader>
						<CardTitle className="text-lg">Set Up Your Project</CardTitle>
					</CardHeader>
					<CardContent className="space-y-6">
						{/* Primary input */}
						<div className="space-y-2">
							<Label htmlFor="primary-input">Company name, URL, GitHub repo, or package name *</Label>
							<div className="flex gap-2">
								<Input
									id="primary-input"
									placeholder="e.g. Acme Corp, github.com/acme/toolkit, acme.io"
									value={primaryInput}
									onChange={(e) => setPrimaryInput(e.target.value)}
									className="flex-1"
								/>
								<Button
									type="button"
									variant="secondary"
									onClick={handleAutofill}
									disabled={!primaryInput.trim() || isAutofilling}
								>
									{isAutofilling ? (
										<>
											<svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
												<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
												<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
											</svg>
											Filling...
										</>
									) : (
										"Fill with AI"
									)}
								</Button>
							</div>
							<p className="text-xs text-muted-foreground">
								AI will search the web to find your product info, competitors, and suggest monitoring terms. Costs less than $0.01.
							</p>
						</div>

						{/* Inline API key prompt */}
						{showApiKeyInput && (
							<Alert>
								<AlertDescription>
									<div className="space-y-3">
										<p className="text-sm">
											An OpenRouter API key is required for AI autofill. Enter your key below, or skip and fill in the fields manually.
										</p>
										<div className="flex gap-2">
											<Input
												type="password"
												placeholder="sk-or-..."
												value={inlineApiKey}
												onChange={(e) => setInlineApiKey(e.target.value)}
												className="flex-1"
											/>
											<Button
												size="sm"
												onClick={handleSaveKeyAndAutofill}
												disabled={!inlineApiKey.trim() || saveApiKey.isPending}
											>
												{saveApiKey.isPending ? "Saving..." : "Save & Fill"}
											</Button>
											<Button
												size="sm"
												variant="ghost"
												onClick={() => setShowApiKeyInput(false)}
											>
												Skip
											</Button>
										</div>
									</div>
								</AlertDescription>
							</Alert>
						)}

						{/* Autofill error */}
						{autofillError && (
							<p className="text-sm text-destructive">{autofillError}</p>
						)}

						<Separator />

						{/* Optional fields */}
						<div className="space-y-4">
							<p className="text-sm text-muted-foreground">
								Optional — these fields will use defaults if left empty.
							</p>

							<div className="grid gap-4 sm:grid-cols-2">
								<div className="space-y-2">
									<Label htmlFor="project-name">Project Name</Label>
									<Input
										id="project-name"
										placeholder={primaryInput.trim() || "Defaults to input above"}
										value={projectName}
										onChange={(e) => setProjectName(e.target.value)}
									/>
								</div>

								<div className="space-y-2">
									<Label htmlFor="brand-name">Brand Name</Label>
									<Input
										id="brand-name"
										placeholder={primaryInput.trim() || "Defaults to input above"}
										value={brandName}
										onChange={(e) => setBrandName(e.target.value)}
									/>
								</div>
							</div>

							<div className="space-y-2">
								<Label htmlFor="description">Description</Label>
								<Textarea
									id="description"
									placeholder="What are you monitoring and why?"
									value={description}
									onChange={(e) => setDescription(e.target.value)}
									rows={2}
								/>
							</div>

							<div className="space-y-2">
								<Label htmlFor="brand-aliases">
									Brand Aliases (comma-separated)
								</Label>
								<Input
									id="brand-aliases"
									placeholder="Acme, Acme Corporation"
									value={brandAliases}
									onChange={(e) => setBrandAliases(e.target.value)}
								/>
							</div>

							<div className="space-y-3">
								<Label>Competitors</Label>
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

							<div className="space-y-3">
								<Label>Monitoring Terms</Label>
								<p className="text-xs text-muted-foreground">
									What would someone ask GPT or Claude when looking for a tool like yours?
								</p>
								<div className="flex gap-2">
									<Input
										placeholder='e.g. "best tool for [your category]"'
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
							</div>

							<Separator />

							<div className="space-y-4">
								<Label className="text-base font-medium">Schedule</Label>
								<div className="grid gap-4 sm:grid-cols-2">
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
										<p className="text-xs text-muted-foreground">Times are in UTC</p>
									</div>

									<div className="space-y-3">
										<Label>Days of Week</Label>
										<div className="grid grid-cols-2 gap-2">
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
								</div>
							</div>
						</div>

						<p className="text-sm text-muted-foreground">
							We'll monitor using 3 default AI models (Claude, GPT, Gemini) via OpenRouter.
							You can customize providers after setup.
						</p>

						{submitError && (
							<p className="text-sm text-destructive">{submitError}</p>
						)}

						<div className="flex justify-end pt-2">
							<Button
								onClick={handleSubmit}
								disabled={!primaryInput.trim() || isSubmitting}
							>
								{isSubmitting ? "Creating Project..." : "Create Project"}
							</Button>
						</div>
					</CardContent>
				</Card>
			)}

			{step === 2 && createdProjectId && (
				<Card>
					<CardContent className="py-10">
						<div className="flex flex-col items-center text-center space-y-6">
							<div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="h-8 w-8 text-green-600 dark:text-green-400">
									<polyline points="20 6 9 17 4 12" />
								</svg>
							</div>
							<div>
								<h2 className="text-xl font-semibold">Project Created</h2>
								<p className="mt-1 text-sm text-muted-foreground">
									Your monitoring project is set up and ready to go.
								</p>
							</div>

							<div className="w-full max-w-md rounded-lg border bg-muted/30 p-4">
								<div className="grid grid-cols-2 gap-3 text-sm">
									<div className="text-left">
										<span className="text-muted-foreground">Project</span>
										<p className="font-medium">{projectName.trim() || primaryInput.trim()}</p>
									</div>
									<div className="text-left">
										<span className="text-muted-foreground">Brand</span>
										<p className="font-medium">{brandName.trim() || primaryInput.trim()}</p>
									</div>
									<div className="text-left">
										<span className="text-muted-foreground">Competitors</span>
										<p className="font-medium">{competitors.length}</p>
									</div>
									<div className="text-left">
										<span className="text-muted-foreground">Terms</span>
										<p className="font-medium">{terms.length}</p>
									</div>
									<div className="col-span-2 text-left">
										<span className="text-muted-foreground">Schedule</span>
										<p className="font-medium">
											{formatHour(hour)} on{" "}
											{days.length === 7
												? "every day"
												: days.map((d) => DAY_NAMES[d]).join(", ")}
										</p>
									</div>
								</div>
							</div>

							<Badge
								variant="secondary"
								className={
									monitorTriggered
										? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
										: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
								}
							>
								{monitorTriggered ? "First scan running" : "Queuing first scan..."}
							</Badge>

							<Button asChild className="mt-2">
								<a href={`/projects/${createdProjectId}`}>Go to Project</a>
							</Button>
						</div>
					</CardContent>
				</Card>
			)}
		</div>
	)
}
