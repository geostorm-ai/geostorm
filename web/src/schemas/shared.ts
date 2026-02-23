import { z } from "zod"

export const PaginatedResponseSchema = <T extends z.ZodTypeAny>(
	itemSchema: T,
) =>
	z.object({
		items: z.array(itemSchema),
		total: z.number(),
		limit: z.number(),
		offset: z.number(),
	})

export type PaginatedResponse<T> = {
	items: T[]
	total: number
	limit: number
	offset: number
}
