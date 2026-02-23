import { test, expect } from "@playwright/test"

test.describe("Dashboard Load", () => {
	test("dashboard redirects to demo project with signal panel", async ({ page }) => {
		await page.goto("/")
		// Should land on a project detail page (demo project)
		await expect(page).toHaveURL(/\/projects\//)
		await expect(page.getByText("GeoStorm Demo: FastAPI")).toBeVisible()
	})

	test("alerts section is visible above the fold", async ({ page }) => {
		await page.goto("/")
		// The alerts feed should be visible on the page
		const alertsSection = page.getByText(/alert/i).first()
		await expect(alertsSection).toBeVisible()
	})

	test("perception data is visible on dashboard", async ({ page }) => {
		await page.goto("/")
		// Perception-related content should be present
		const perceptionContent = page.getByText(/recommendation share|perception|score/i).first()
		await expect(perceptionContent).toBeVisible()
	})

	test("navigation sidebar is present with project list", async ({ page }) => {
		await page.goto("/")
		// Should see navigation elements
		await expect(page.getByText("Projects")).toBeVisible()
		await expect(page.getByText("Settings")).toBeVisible()
	})

	test("demo project API returns perception data for chart", async ({ request }) => {
		const projectsResponse = await request.get("/api/projects")
		const projects = await projectsResponse.json()
		const demoProject = projects.find((p: { is_demo: boolean }) => p.is_demo)
		expect(demoProject).toBeTruthy()

		const perceptionResponse = await request.get(`/api/projects/${demoProject.id}/perception`)
		expect(perceptionResponse.status()).toBe(200)
		const perception = await perceptionResponse.json()
		expect(perception.data.length).toBeGreaterThan(0)
	})

	test("health endpoint reports healthy status", async ({ request }) => {
		const response = await request.get("/health")
		expect(response.status()).toBe(200)
		const data = await response.json()
		expect(data.status).toBe("ok")
		expect(data.database).toBe("connected")
		expect(data.scheduler).toBe("running")
	})
})
