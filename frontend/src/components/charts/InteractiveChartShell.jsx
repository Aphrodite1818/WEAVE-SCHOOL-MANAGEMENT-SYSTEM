import { useEffect, useState } from "react";
import { Maximize2, X } from "lucide-react";

function InteractiveChartShell({
  title,
  description,
  children,
  expandedChildren,
  hint = "Scroll, swipe, or expand this chart.",
}) {
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!expanded || typeof document === "undefined") return undefined;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event) => {
      if (event.key === "Escape") setExpanded(false);
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [expanded]);

  return (
    <div className="dashboard-chart-card flex min-h-[22rem] flex-col overflow-hidden p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold leading-6 text-text">{title}</h3>
          {description ? <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p> : null}
          <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-text-faint sm:text-xs">
            {hint}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2 text-xs font-semibold text-text-muted transition hover:border-primary/40 hover:bg-primary-subtle/20 hover:text-primary"
          aria-label={`Expand ${title}`}
        >
          <Maximize2 className="h-4 w-4" />
          <span className="hidden sm:inline">Expand</span>
        </button>
      </div>

      {children}

      {expanded ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={title}
          className="fixed inset-0 z-[100] bg-background/95 p-3 backdrop-blur-md sm:p-6"
        >
          <div className="mx-auto flex h-full w-full max-w-7xl flex-col overflow-hidden rounded-[1.5rem] border border-border bg-surface shadow-2xl">
            <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
              <div className="min-w-0">
                <h2 className="text-base font-semibold leading-6 text-text sm:text-lg">{title}</h2>
                {description ? <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p> : null}
              </div>
              <button
                type="button"
                onClick={() => setExpanded(false)}
                className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-border bg-surface-muted/45 text-text-muted transition hover:text-text"
                aria-label="Close expanded chart"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="chart-interactive-scroll min-h-0 flex-1 p-3 sm:p-5">
              {expandedChildren || children}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default InteractiveChartShell;
