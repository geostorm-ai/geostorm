import type { RunProgressEvent } from "@/schemas/progress"

interface RunProgressPipelineProps {
	progress: RunProgressEvent
}

const phases = ["preparing", "querying", "analyzing", "complete"] as const

const nodes = [
	{
		id: "preparing",
		label: "Preparing",
		x: 140,
		icon: (
			<>
				<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
				<circle cx="12" cy="12" r="3" />
			</>
		),
	},
	{
		id: "querying",
		label: "Querying LLMs",
		x: 313,
		icon: (
			<>
				<rect x="3" y="11" width="18" height="10" rx="2" />
				<circle cx="12" cy="5" r="2" />
				<path d="M12 7v4" />
				<line x1="8" y1="16" x2="8" y2="16" />
				<line x1="16" y1="16" x2="16" y2="16" />
			</>
		),
	},
	{
		id: "analyzing",
		label: "Analyzing",
		x: 486,
		icon: (
			<>
				<circle cx="11" cy="11" r="8" />
				<line x1="21" y1="21" x2="16.65" y2="16.65" />
			</>
		),
	},
	{
		id: "complete",
		label: "Done",
		x: 660,
		icon: <polyline points="20 6 9 17 4 12" />,
	},
]

export function RunProgressPipeline({ progress }: RunProgressPipelineProps) {
	const { phase, completed, failed, total, current_term, current_provider } =
		progress

	// Map "failed" phase to the last node index (same as "complete")
	const currentIndex = phase === "failed"
		? phases.length - 1
		: Math.max(0, phases.indexOf(phase as (typeof phases)[number]))
	const isDone = phase === "complete" || phase === "failed"

	const numTotal = Math.max(1, total)
	const gap = numTotal > 40 ? 1 : 3
	const segmentWidth = (400 - (numTotal - 1) * gap) / numTotal

	let displayStatus: string
	if (phase === "preparing") displayStatus = "Initializing environment..."
	else if (phase === "querying") {
		displayStatus =
			current_provider && current_term
				? `Querying ${current_provider} for "${current_term}"...`
				: "Querying language models..."
	} else if (phase === "analyzing") displayStatus = "Analyzing aggregate results..."
	else if (phase === "failed") displayStatus = "Pipeline failed."
	else displayStatus = "Pipeline complete."

	return (
		<svg
			viewBox="0 0 800 230"
			className="w-full h-auto"
			role="img"
			aria-label={`Pipeline status: ${phase}, ${completed} of ${total} queries completed`}
		>
			<defs>
				<filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
					<feGaussianBlur stdDeviation="3" result="blur" />
					<feComposite
						in="SourceGraphic"
						in2="blur"
						operator="over"
					/>
				</filter>
				<linearGradient
					id="completed-grad"
					x1="0"
					y1="0"
					x2="1"
					y2="1"
				>
					<stop
						offset="0%"
						stopColor="hsl(var(--primary))"
						stopOpacity="0.15"
					/>
					<stop
						offset="100%"
						stopColor="hsl(var(--primary))"
						stopOpacity="0.03"
					/>
				</linearGradient>
			</defs>

			{/* Connecting Lines */}
			{nodes.map((node, i) => {
				if (i === nodes.length - 1) return null
				const nextNode = nodes[i + 1]
				const x1 = node.x + 34
				const x2 = nextNode.x - 34
				const isLinkCompleted = currentIndex > i || isDone
				const isLinkActive = currentIndex === i && !isDone

				return (
					<g key={`link-${node.id}`}>
						<line
							x1={x1}
							y1="80"
							x2={x2}
							y2="80"
							stroke={
								isLinkCompleted || isLinkActive
									? "hsl(var(--primary))"
									: "hsl(var(--border))"
							}
							strokeWidth="3"
							strokeDasharray={
								isLinkActive
									? "8 8"
									: isLinkCompleted
										? "none"
										: "6 6"
							}
							opacity={isLinkCompleted ? 0.6 : 1}
						>
							{isLinkActive && (
								<animate
									attributeName="stroke-dashoffset"
									from="16"
									to="0"
									dur="0.8s"
									repeatCount="indefinite"
								/>
							)}
						</line>
						{isLinkActive && (
							<circle
								cy="80"
								r="4"
								fill="hsl(var(--primary))"
								filter="url(#glow)"
							>
								<animate
									attributeName="cx"
									values={`${String(x1)};${String(x2)}`}
									dur="1.5s"
									repeatCount="indefinite"
								/>
								<animate
									attributeName="opacity"
									values="0;1;1;0"
									keyTimes="0;0.1;0.9;1"
									dur="1.5s"
									repeatCount="indefinite"
								/>
							</circle>
						)}
					</g>
				)
			})}

			{/* Nodes */}
			{nodes.map((node, i) => {
				const isNodeCompleted = currentIndex > i || isDone
				const isNodeActive = currentIndex === i && !isDone
				const isFinalFailed = phase === "failed" && i === nodes.length - 1

				return (
					<g key={node.id} transform={`translate(${String(node.x)}, 80)`}>
						{/* Active Glow Pulse */}
						{isNodeActive && (
							<circle
								r="32"
								fill="hsl(var(--primary))"
								filter="url(#glow)"
							>
								<animate
									attributeName="opacity"
									values="0.1;0.35;0.1"
									dur="2s"
									repeatCount="indefinite"
								/>
							</circle>
						)}

						<circle
							r="24"
							fill={
								isNodeCompleted
									? "url(#completed-grad)"
									: "hsl(var(--background, 0 0% 100%))"
							}
							stroke={
								isFinalFailed
									? "hsl(var(--destructive, 0 84% 60%))"
									: isNodeCompleted || isNodeActive
										? "hsl(var(--primary))"
										: "hsl(var(--border))"
							}
							strokeWidth={isNodeActive ? "3" : "2"}
						/>

						<g
							transform="translate(-12, -12)"
							fill="none"
							stroke={
								isFinalFailed
									? "hsl(var(--destructive, 0 84% 60%))"
									: isNodeCompleted || isNodeActive
										? "hsl(var(--primary))"
										: "hsl(var(--muted-foreground))"
							}
							strokeWidth="2"
							strokeLinecap="round"
							strokeLinejoin="round"
						>
							{node.icon}
						</g>

						<text
							y="45"
							textAnchor="middle"
							fill={
								isNodeActive || isNodeCompleted
									? "hsl(var(--foreground))"
									: "hsl(var(--muted-foreground))"
							}
							fontSize="14"
							fontWeight={isNodeActive ? "600" : "400"}
						>
							{node.label}
						</text>
					</g>
				)
			})}

			{/* Dynamic Status Section */}
			<g transform="translate(400, 165)">
				<text
					textAnchor="middle"
					fill="hsl(var(--foreground))"
					fontSize="15"
					fontWeight="500"
				>
					{displayStatus}
				</text>

				{/* Segmented Progress Bar */}
				{(phase === "querying" || phase === "analyzing") && total > 0 && (
					<g transform="translate(-200, 15)">
						{Array.from({ length: numTotal }).map((_, i) => {
							let fill = "hsl(var(--muted))"
							let isPulsing = false

							if (i < completed) fill = "hsl(var(--primary))"
							else if (i < completed + failed)
								fill = "hsl(var(--destructive, 0 84.2% 60.2%))"
							else if (
								i === completed + failed &&
								phase === "querying"
							) {
								fill = "hsl(var(--primary))"
								isPulsing = true
							}

							return (
								<rect
									key={`seg-${String(i)}`}
									x={i * (segmentWidth + gap)}
									y="0"
									width={segmentWidth}
									height="8"
									rx="2"
									fill={fill}
								>
									{isPulsing && (
										<animate
											attributeName="opacity"
											values="0.3;1;0.3"
											dur="1.5s"
											repeatCount="indefinite"
										/>
									)}
								</rect>
							)
						})}
					</g>
				)}

				{/* Sub-status Counts */}
				{(phase === "querying" || phase === "analyzing") && total > 0 && (
					<text
						y="42"
						textAnchor="middle"
						fontSize="13"
						fill="hsl(var(--muted-foreground))"
					>
						{completed} completed
						{failed > 0 && (
							<tspan fill="hsl(var(--destructive, 0 84.2% 60.2%))">
								, {failed} failed
							</tspan>
						)}
						<tspan>{` \u2022 ${total} total`}</tspan>
					</text>
				)}
			</g>
		</svg>
	)
}
