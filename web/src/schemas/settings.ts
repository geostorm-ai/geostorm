import { z } from "zod"

export const StoreApiKeyRequestSchema = z.object({
	key: z.string().min(1),
})

export type StoreApiKeyRequest = z.infer<typeof StoreApiKeyRequestSchema>
