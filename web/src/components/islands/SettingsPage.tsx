import { QueryProvider } from "@/components/providers/QueryProvider"
import { APIKeySettings } from "./APIKeySettings"

export function SettingsPage() {
	return (
		<div className="p-6 max-w-2xl">
			<h1 className="text-2xl font-bold mb-6">Settings</h1>
			<QueryProvider>
				<APIKeySettings />
			</QueryProvider>
		</div>
	)
}
