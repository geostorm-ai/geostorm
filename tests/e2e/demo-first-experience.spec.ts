import { test, expect } from "@playwright/test"

test.describe("Demo First Experience", () => {
	test("loads demo project immediately on first visit", async ({ page }) => {
		await page.goto("/")
		// Should redirect to the demo project detail page
		await expect(page).toHaveURL(/\/projects\//)
		await expect(page.getByText("GeoStorm Demo: FastAPI")).toBeVisible()
	})

	test("does not show setup wizard on fresh database", async ({ page }) => {
		await page.goto("/")
		await expect(page.getByText("Setup Wizard")).not.toBeVisible()
		await expect(page.getByText("Welcome to GeoStorm")).not.toBeVisible()
	})

	test("shows API key banner prompting user to add key", async ({ page }) => {
		await page.goto("/")
		await expect(page.getByText("Add your OpenRouter API key")).toBeVisible()
	})

	test("demo project is marked read-only", async ({ page }) => {
		await page.goto("/")
		await expect(page.getByText("read-only demo project")).toBeVisible()
	})

	test("can explore demo alerts via API", async ({ request }) => {
		const response = await request.get("/api/alerts?limit=5")
		expect(response.status()).toBe(200)
		const data = await response.json()
		expect(data.items.length).toBeGreaterThan(0)
	})

	test("can explore demo runs via API", async ({ request }) => {
		const projectsResponse = await request.get("/api/projects")
		const projects = await projectsResponse.json()
		const demoProject = projects.find((p: { is_demo: boolean }) => p.is_demo)
		expect(demoProject).toBeTruthy()

		const runsResponse = await request.get(`/api/projects/${demoProject.id}/runs`)
		expect(runsResponse.status()).toBe(200)
	})

	test("can explore demo perception data via API", async ({ request }) => {
		const projectsResponse = await request.get("/api/projects")
		const projects = await projectsResponse.json()
		const demoProject = projects.find((p: { is_demo: boolean }) => p.is_demo)
		expect(demoProject).toBeTruthy()

		const perceptionResponse = await request.get(`/api/projects/${demoProject.id}/perception`)
		expect(perceptionResponse.status()).toBe(200)
		const data = await perceptionResponse.json()
		expect(data.data.length).toBeGreaterThan(0)
	})
})
