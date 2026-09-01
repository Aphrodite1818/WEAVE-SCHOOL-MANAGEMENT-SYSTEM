import { GraduationCap, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { academicLevelService } from "../../services/academicsService";
import { cn } from "../../utils/cn";
import { filterDepartmentWorkflow } from "./academicDepartmentCapability";
import {
  academicWorkflowConfig,
  academicWorkflowOrder,
} from "./academicWorkflowConfig";

const asItems = (value) => (Array.isArray(value) ? value : value?.items || []);

export default function AcademicOrbitNavigator({
  currentWorkflow = "",
  workflows,
}) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [fallbackWorkflows, setFallbackWorkflows] = useState(() =>
    filterDepartmentWorkflow(academicWorkflowOrder, []),
  );
  const visibleWorkflows = Array.isArray(workflows)
    ? workflows
    : fallbackWorkflows;

  useEffect(() => {
    if (Array.isArray(workflows)) return undefined;

    let mounted = true;
    academicLevelService
      .getCategories()
      .then((response) => {
        if (mounted) {
          setFallbackWorkflows(
            filterDepartmentWorkflow(academicWorkflowOrder, asItems(response)),
          );
        }
      })
      .catch(() => {
        if (mounted) {
          setFallbackWorkflows(
            filterDepartmentWorkflow(academicWorkflowOrder, []),
          );
        }
      });

    return () => {
      mounted = false;
    };
  }, [workflows]);

  const selectWorkflow = (workflow) => {
    setOpen(false);
    navigate(`/admin/academic/${workflow}`);
  };

  return (
    <>
      {open ? (
        <button
          type="button"
          aria-label="Close academic navigation"
          className="fixed inset-0 z-40 cursor-default bg-slate-950/[0.04] backdrop-blur-[1px]"
          onClick={() => setOpen(false)}
        />
      ) : null}

      <div
        data-academic-workflow-navigator="true"
        className="fixed bottom-4 right-3 z-50 sm:right-6 md:bottom-6"
      >
        {open ? (
          <div
            data-academic-workflow-menu="true"
            className="mb-3 flex max-h-[65dvh] w-[min(23rem,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl"
          >
            <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border/70 px-3.5 py-3">
              <div className="min-w-0">
                <p className="text-sm font-bold text-text">Academic navigation</p>
                <p className="mt-0.5 text-[11px] leading-4 text-text-muted">
                  Jump to any academic workspace.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-border/70 text-text-muted transition hover:bg-surface-muted hover:text-text"
                aria-label="Close academic navigation"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-2 overflow-y-auto overscroll-contain p-3">
              {visibleWorkflows.map((workflow) => {
                const config = academicWorkflowConfig[workflow];
                const Icon = config.icon;
                const active = workflow === currentWorkflow;
                return (
                  <button
                    key={workflow}
                    type="button"
                    title={config.title}
                    aria-label={`Open ${config.title}`}
                    aria-current={active ? "page" : undefined}
                    onClick={() => selectWorkflow(workflow)}
                    className={cn(
                      "flex min-h-[4.75rem] min-w-0 flex-col items-center justify-center gap-1.5 rounded-xl border px-2 py-2.5 text-center transition",
                      active
                        ? "border-primary/35 bg-primary-soft text-primary"
                        : "border-border/70 bg-surface text-text-soft hover:border-primary/25 hover:bg-surface-muted hover:text-text",
                    )}
                  >
                    <span
                      className={cn(
                        "grid h-8 w-8 shrink-0 place-items-center rounded-lg",
                        active ? "bg-primary/10" : "bg-surface-muted",
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="w-full break-words text-[11px] font-semibold leading-4">
                      {config.shortTitle || config.title}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}

        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-label={open ? "Close academic navigation" : "Open academic navigation"}
          className={cn(
            "ml-auto grid h-14 w-14 place-items-center rounded-full border-[5px] border-primary-soft bg-primary text-white shadow-xl transition hover:scale-105",
            open && "shadow-lg",
          )}
        >
          {open ? <X className="h-5 w-5" /> : <GraduationCap className="h-5 w-5" />}
        </button>
      </div>
    </>
  );
}
