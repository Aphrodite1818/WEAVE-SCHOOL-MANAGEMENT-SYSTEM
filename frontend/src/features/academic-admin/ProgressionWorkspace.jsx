import { ArrowRight, GraduationCap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import LoadingState from "../../components/shared/LoadingState";
import { useToast } from "../../hooks/useToast";
import { academicLevelService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { WorkspacePanel } from "./AcademicWorkspacePrimitives";

const CATEGORY_ORDER = [
  "KINDERGARTEN",
  "PRIMARY",
  "JUNIOR_SECONDARY",
  "SENIOR_SECONDARY",
];

const categoryLabel = (value) =>
  String(value || "")
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const asItems = (response) =>
  Array.isArray(response) ? response : response?.items || [];

function ProgressionWorkspace() {
  const { showError } = useToast();
  const [levels, setLevels] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    academicLevelService
      .getLevels()
      .then((response) => {
        if (active) setLevels(asItems(response));
      })
      .catch((error) => {
        if (active) showError(getErrorMessage(error, "Could not load automatic progression."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [showError]);

  const orderedLevels = useMemo(
    () =>
      [...levels].sort((left, right) => {
        const categoryDifference =
          CATEGORY_ORDER.indexOf(left.category) - CATEGORY_ORDER.indexOf(right.category);
        return categoryDifference || left.position - right.position;
      }),
    [levels],
  );

  if (loading) return <LoadingState label="Loading automatic progression..." />;

  return (
    <WorkspacePanel
      title="Automatic level transitions"
      description="This is a read-only view. Category and position determine the next level; class, arm, and department never affect progression."
    >
      {orderedLevels.length ? (
        <div className="space-y-3">
          {orderedLevels.map((level, index) => {
            const nextLevel = orderedLevels[index + 1] || null;
            return (
              <div
                key={level.id}
                className="grid gap-3 rounded-2xl border border-border/70 bg-surface p-4 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-center"
              >
                <div>
                  <p className="font-semibold text-text">{level.name}</p>
                  <p className="mt-1 text-sm text-text-muted">
                    {categoryLabel(level.category)} · Position {level.position}
                  </p>
                </div>
                <ArrowRight className="hidden h-5 w-5 text-text-faint sm:block" aria-hidden="true" />
                {nextLevel ? (
                  <div>
                    <Badge variant="success">Next level</Badge>
                    <p className="mt-2 font-semibold text-text">{nextLevel.name}</p>
                    <p className="mt-1 text-sm text-text-muted">
                      {categoryLabel(nextLevel.category)} · Position {nextLevel.position}
                    </p>
                  </div>
                ) : (
                  <div>
                    <Badge variant="primary">Completion</Badge>
                    <p className="mt-2 flex items-center gap-2 font-semibold text-text">
                      <GraduationCap className="h-4 w-4" aria-hidden="true" />
                      Graduate
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-text-muted">
          Create an academic level to preview progression.
        </div>
      )}
    </WorkspacePanel>
  );
}

export default ProgressionWorkspace;
