function getApiBase(): string {
	if (import.meta.env.PUBLIC_API_URL) {
		return import.meta.env.PUBLIC_API_URL
	}
	// Server-side (SSR) cannot resolve relative URLs — use absolute
	if (typeof window === "undefined") {
		return "http://localhost:8080/api"
	}
	return "/api"
}

export class ApiError extends Error {
	status: number
	body: unknown

	constructor(status: number, message: string, body?: unknown) {
		super(message)
		this.name = "ApiError"
		this.status = status
		this.body = body
	}
}

export async function apiFetch<T>(
	path: string,
	options?: RequestInit,
): Promise<T> {
	const base = getApiBase()
	const response = await fetch(`${base}${path}`, {
		headers: { "Content-Type": "application/json", ...options?.headers },
		...options,
	})
	if (!response.ok) {
		let body: unknown
		try {
			body = await response.json()
		} catch {
			body = await response.text()
		}
		throw new ApiError(response.status, `API error: ${response.status}`, body)
	}
	if (response.status === 204) {
		return undefined as T
	}
	return response.json() as Promise<T>
}
