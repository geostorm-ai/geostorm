import { test, expect } from "@playwright/test"

test.describe("API Key Setup Workflow", () => {
	test("settings page loads with API key input", async ({ page }) => {
		await page.goto("/settings")
		await expect(page.getByText("API Key")).toBeVisible()
	})

	test("can save an API key via API", async ({ request }) => {
		const response = await request.post("/api/settings/api-key", {
			data: { key: "sk-or-v1-test-key-for-e2e" },
		})
		expect(response.status()).toBe(200)

		// Verify key is now configured
		const statusResponse = await request.get("/api/settings/api-key-status")
		expect(statusResponse.status()).toBe(200)
		const status = await statusResponse.json()
		expect(status.configured).toBe(true)
	})

	test("setup status reflects API key presence", async ({ request }) => {
		// First, ensure key is stored
		await request.post("/api/settings/api-key", {
			data: { key: "sk-or-v1-test-key-for-e2e" },
		})

		const response = await request.get("/api/setup/status")
		expect(response.status()).toBe(200)
		const status = await response.json()
		expect(status.has_api_key).toBe(true)
	})

	test("create project button links to setup page", async ({ page }) => {
		await page.goto("/projects")
		const createButton = page.getByRole("link", { name: /create project/i })
		await expect(createButton).toBeVisible()
		await createButton.click()
		await expect(page).toHaveURL(/\/setup/)
	})

	test("can delete an API key via API", async ({ request }) => {
		// Store a key first
		await request.post("/api/settings/api-key", {
			data: { key: "sk-or-v1-test-key-to-delete" },
		})

		// Delete it
		const deleteResponse = await request.delete("/api/settings/api-key")
		expect(deleteResponse.status()).toBe(200)

		// Verify key is gone
		const statusResponse = await request.get("/api/settings/api-key-status")
		const status = await statusResponse.json()
		expect(status.configured).toBe(false)
	})
})
