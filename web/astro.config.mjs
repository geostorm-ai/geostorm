// @ts-check

import react from "@astrojs/react"
import tailwind from "@astrojs/tailwind"
import { defineConfig } from "astro/config"

// https://astro.build/config
export default defineConfig({
	output: "static",
	integrations: [react(), tailwind({ applyBaseStyles: false })],
	vite: {
		server: {
			proxy: {
				"/api": {
					target: "http://localhost:8080",
					changeOrigin: true,
				},
			},
		},
	},
})
