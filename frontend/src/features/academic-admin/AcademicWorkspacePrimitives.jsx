import { Edit3 } from "lucide-react";

import EmptyState from "../../components/shared/EmptyState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { cn } from "../../utils/cn";

export function WorkspaceGrid({ editor, content, wide = false }) {
  if (!editor || !content) {
    return (
      <section className="grid gap-4">
        <div className="min-w-0">{editor || content}</div>
      </section>
    );
  }

  return (
    <section
      className={cn(
        "grid gap-4",
        wide
          ? "2xl:grid-cols-[minmax(340px,0.8fr)_minmax(0,1.6fr)]"
          : "xl:grid-cols-[minmax(320px,0.85fr)_minmax(0,1.35fr)]",
      )}
    >
      <div className="min-w-0">{editor}</div>
      <div className="min-w-0">{content}</div>
    </section>
  );
}

export function WorkspacePanel({ title, description, children, actions }) {
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="section-title">{title}</h3>
          {description ? (
            <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="w-full sm:w-auto sm:max-w-xs sm:shrink-0">{actions}</div> : null}
      </div>
      <div className="mt-4">{children}</div>
    </Card>
  );
}

export function SelectControl({
  label,
  value,
  onChange,
  options,
  placeholder = "Select an option",
  required = false,
  disabled = false,
  error,
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-text-soft">
        {label}
      </span>
      <select
        value={value || ""}
        onChange={(event) => onChange(event.target.value)}
        className="input-base"
        required={required}
        disabled={disabled}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error ? <span className="mt-1 block text-xs text-error">{error}</span> : null}
    </label>
  );
}

export function CheckboxControl({ label, checked, onChange, disabled = false }) {
  return (
    <label className="flex min-h-11 items-center gap-3 rounded-xl border border-border/70 bg-surface px-3 py-2 text-sm font-medium text-text-soft">
      <input
        type="checkbox"
        checked={Boolean(checked)}
        onChange={(event) => onChange(event.target.checked)}
        disabled={disabled}
        className="h-4 w-4 rounded border-border accent-primary"
      />
      {label}
    </label>
  );
}

export function FormActions({
  submitting,
  submitLabel,
  editing = false,
  onCancel,
  disabled = false,
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <Button type="submit" disabled={submitting || disabled}>
        {submitting ? "Saving..." : submitLabel}
      </Button>
      {editing ? (
        <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
      ) : null}
    </div>
  );
}

const badgeVariant = (status) => {
  const value = String(status || "").toLowerCase();
  if (["active", "current", "submitted", "published", "complete"].includes(value)) {
    return "success";
  }
  if (["draft", "pending", "read_only"].includes(value)) return "warning";
  if (["inactive", "ended", "failed", "revoked"].includes(value)) return "error";
  return "default";
};

export function RecordList({
  title,
  description,
  items,
  emptyTitle,
  emptyDescription,
  emptyIcon,
  renderTitle,
  renderMeta,
  renderDescription,
  renderStatus,
  renderActions,
  onEdit,
  canEdit,
  actions,
  listClassName,
}) {
  return (
    <WorkspacePanel title={title} description={description} actions={actions}>
      {items.length === 0 ? (
        <EmptyState
          icon={emptyIcon}
          title={emptyTitle}
          description={emptyDescription}
        />
      ) : (
        <div
          className={cn(
            "mobile-scroll-list record-list-grid grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-3",
            listClassName,
          )}
        >
          {items.map((item) => {
            const status = renderStatus?.(item);
            const showEdit = Boolean(onEdit) && (canEdit ? canEdit(item) : true);
            return (
              <div
                key={item.id}
                className="flex min-h-[9rem] flex-col rounded-2xl border border-border/70 bg-surface px-4 py-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="break-words text-sm font-semibold text-text">
                      {renderTitle(item)}
                    </p>
                    {renderMeta ? (
                      <p className="mt-1 break-words text-xs text-text-muted">
                        {renderMeta(item)}
                      </p>
                    ) : null}
                  </div>
                  {status ? (
                    <Badge variant={badgeVariant(status)} title={String(status).replaceAll("_", " ")}>
                      {String(status).replaceAll("_", " ")}
                    </Badge>
                  ) : null}
                </div>
                {renderDescription ? (
                  <p className="mt-3 line-clamp-3 text-sm leading-6 text-text-muted">
                    {renderDescription(item)}
                  </p>
                ) : null}
                {showEdit || renderActions ? (
                  <div className="mt-auto flex flex-wrap gap-2 pt-4">
                    {renderActions ? renderActions(item) : null}
                    {showEdit ? (
                    <Button
                      type="button"
                      size="small"
                      variant="outline"
                      onClick={() => onEdit(item)}
                    >
                      <Edit3 className="h-4 w-4" />
                      Edit
                    </Button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </WorkspacePanel>
  );
}

export { Input };
