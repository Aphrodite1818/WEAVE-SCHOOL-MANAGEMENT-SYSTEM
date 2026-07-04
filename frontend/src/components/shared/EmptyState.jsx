import { Inbox } from "lucide-react";
import Button from "../ui/Button";

function EmptyState({
  icon: Icon = Inbox,
  title = "Nothing here yet",
  actionLabel,
  onAction,
}) {
  return (
    <div className="flex min-h-44 flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface-muted/50 px-6 py-10 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-soft text-primary">
        <Icon className="h-5 w-5" />
      </span>
      <h3 className="mt-4 text-base font-semibold">{title}</h3>
      {actionLabel && onAction && (
        <Button type="button" className="mt-5" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

export default EmptyState;
