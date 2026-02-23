import { cn } from "@/lib/utils"

interface EmptyStateProps {
	icon?: React.ReactNode
	title: string
	description?: string
	action?: React.ReactNode
	className?: string
}

export function EmptyState({
	icon,
	title,
	description,
	action,
	className,
}: EmptyStateProps) {
	return (
		<div
			className={cn(
				"flex flex-col items-center justify-center gap-3 py-12 text-center",
				className,
			)}
		>
			{icon && <div className="text-muted-foreground">{icon}</div>}
			<h3 className="text-lg font-semibold">{title}</h3>
			{description && (
				<p className="max-w-sm text-sm text-muted-foreground">{description}</p>
			)}
			{action && <div className="mt-2">{action}</div>}
		</div>
	)
}
