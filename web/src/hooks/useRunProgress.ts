import { useEffect, useRef, useState } from "react"
import {
	RunProgressEventSchema,
	type RunProgressEvent,
} from "@/schemas/progress"

function getApiBase(): string {
	if (typeof window === "undefined") return "http://localhost:8080/api"
	if (import.meta.env.PUBLIC_API_URL) return import.meta.env.PUBLIC_API_URL
	return "/api"
}

export function useRunProgress(
	runId: string | null | undefined,
	enabled = true,
) {
	const [progress, setProgress] = useState<RunProgressEvent | null>(null)
	const eventSourceRef = useRef<EventSource | null>(null)

	useEffect(() => {
		if (!runId || !enabled) {
			setProgress(null)
			return
		}

		const base = getApiBase()
		const url = `${base}/runs/${runId}/progress`
		const es = new EventSource(url)
		eventSourceRef.current = es

		es.onmessage = (event) => {
			try {
				const parsed = RunProgressEventSchema.parse(JSON.parse(event.data))
				setProgress(parsed)
				// Auto-close when run finishes
				if (
					parsed.phase === "complete" ||
					parsed.phase === "failed"
				) {
					es.close()
				}
			} catch {
				// Ignore malformed events
			}
		}

		es.onerror = () => {
			// EventSource will auto-reconnect on transient errors.
			// If the stream has ended server-side, close cleanly.
			if (es.readyState === EventSource.CLOSED) {
				es.close()
			}
		}

		return () => {
			es.close()
			eventSourceRef.current = null
		}
	}, [runId, enabled])

	return progress
}
