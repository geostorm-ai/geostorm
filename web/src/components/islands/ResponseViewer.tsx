import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useRunResponses } from "@/hooks/useRuns"

interface ResponseViewerProps {
	runId: string
}

export function ResponseViewer({ runId }: ResponseViewerProps) {
	const { data, isLoading } = useRunResponses(runId)

	if (isLoading) {
		return (
			<div className="space-y-4">
				{[1, 2, 3].map((i) => (
					<div key={i} className="space-y-2">
						<Skeleton className="h-5 w-48" />
						<Skeleton className="h-20 w-full" />
					</div>
				))}
			</div>
		)
	}

	const responses = data?.items ?? []

	if (responses.length === 0) {
		return (
			<p className="py-8 text-center text-sm text-muted-foreground">
				No responses for this run.
			</p>
		)
	}

	return (
		<div className="space-y-4">
			{responses.map((response) => (
				<Card key={response.id}>
					<CardHeader className="pb-2">
						<div className="flex items-center justify-between">
							<CardTitle className="text-sm font-medium">
								{response.model_name}
							</CardTitle>
							<div className="flex items-center gap-2">
								{response.latency_ms != null && (
									<span className="text-xs text-muted-foreground">
										{response.latency_ms}ms
									</span>
								)}
								{response.error_message && (
									<Badge variant="destructive" className="text-xs">
										Error
									</Badge>
								)}
							</div>
						</div>
					</CardHeader>
					<CardContent className="space-y-3">
						{response.error_message ? (
							<p className="text-sm text-destructive">{response.error_message}</p>
						) : (
							<div className="prose prose-sm dark:prose-invert max-w-none overflow-x-auto">
								<ReactMarkdown remarkPlugins={[remarkGfm]}>
									{response.response_text}
								</ReactMarkdown>
							</div>
						)}
						{response.mentions.length > 0 && (
							<div className="flex flex-wrap gap-1.5">
								{response.mentions.map((mention) => (
									<Badge
										key={mention.id}
										variant="secondary"
										className={
											mention.mention_type === "brand"
												? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
												: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
										}
									>
										{mention.target_name}
										{mention.list_position != null && ` #${mention.list_position}`}
									</Badge>
								))}
							</div>
						)}
					</CardContent>
				</Card>
			))}
		</div>
	)
}
