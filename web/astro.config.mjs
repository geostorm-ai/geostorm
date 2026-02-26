// @ts-check

import react from "@astrojs/react"
import tailwind from "@astrojs/tailwind"
import { defineConfig } from "astro/config"

/** Vite plugin: rewrite /projects/<id> to /projects/detail during dev */
function spaFallback() {
	return {
		name: "spa-fallback",
		/** @param {any} server */
		configureServer(server) {
			server.middlewares.use((/** @type {any} */ req, /** @type {any} */ _res, /** @type {any} */ next) => {
				if (
					req.url &&
					req.url.startsWith("/projects/") &&
					!req.url.startsWith("/projects/detail") &&
					req.url !== "/projects/" &&
					req.url !== "/projects"
				) {
					req.url = "/projects/detail"
				}
				next()
			})
		},
	}
}

// https://astro.build/config
export default defineConfig({
	output: "static",
	integrations: [react(), tailwind({ applyBaseStyles: false })],
	vite: {
		plugins: [spaFallback()],
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
