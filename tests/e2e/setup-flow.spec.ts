import { test, expect } from "@playwright/test"

test.describe("Setup Flow - Complete Onboarding", () => {
	test("setup page loads with wizard form", async ({ page }) => {
		await page.goto("/setup")
		await expect(page.getByText("Create")).toBeVisible()
	})

	test("can create a project via API (simulates wizard completion)", async ({ request }) => {
		const response = await request.post("/api/projects", {
			data: {
				name: "E2E Test Project",
				brand_name: "TestSDK",
				brand_aliases: ["test-sdk", "testsdk"],
			},
		})
		expect(response.status()).toBe(201)
		const data = await response.json()
		expect(data.id).toBeTruthy()
		expect(data.name).toBe("E2E Test Project")
		expect(data.brand_id).toBeTruthy()
		expect(data.schedule_id).toBeTruthy()
	})

	test("newly created project appears in project list", async ({ request }) => {
		// Create a project
		const createResponse = await request.post("/api/projects", {
			data: {
				name: "Setup Flow Test",
				brand_name: "FlowBrand",
			},
		})
		expect(createResponse.status()).toBe(201)
		const created = await createResponse.json()

		// Verify it appears in list
		const listResponse = await request.get("/api/projects")
		expect(listResponse.status()).toBe(200)
		const projects = await listResponse.json()
		const found = projects.find((p: { id: string }) => p.id === created.id)
		expect(found).toBeTruthy()
		expect(found.name).toBe("Setup Flow Test")
	})

	test("can add terms to a new project", async ({ request }) => {
		const createResponse = await request.post("/api/projects", {
			data: { name: "Terms Test", brand_name: "TermBrand" },
		})
		const project = await createResponse.json()

		const termResponse = await request.post(`/api/projects/${project.id}/terms`, {
			data: { name: "best testing framework" },
		})
		expect(termResponse.status()).toBe(201)

		const listResponse = await request.get(`/api/projects/${project.id}/terms`)
		expect(listResponse.status()).toBe(200)
		const terms = await listResponse.json()
		expect(terms.length).toBe(1)
		expect(terms[0].name).toBe("best testing framework")
	})

	test("can configure schedule for a new project", async ({ request }) => {
		const createResponse = await request.post("/api/projects", {
			data: { name: "Schedule Test", brand_name: "SchedBrand" },
		})
		const project = await createResponse.json()

		const scheduleResponse = await request.patch(`/api/projects/${project.id}/schedule`, {
			data: { hour_of_day: 8, days_of_week: [0, 1, 2, 3, 4] },
		})
		expect(scheduleResponse.status()).toBe(200)
		const schedule = await scheduleResponse.json()
		expect(schedule.hour_of_day).toBe(8)
	})
})
