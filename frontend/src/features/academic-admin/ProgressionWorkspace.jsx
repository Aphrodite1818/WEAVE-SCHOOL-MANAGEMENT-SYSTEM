import { AlertTriangle, ArrowRight, GraduationCap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import LoadingState from "../../components/shared/LoadingState";
import { useToast } from "../../hooks/useToast";
import { academicLevelService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { WorkspacePanel } from "./AcademicWorkspacePrimitives";

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
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([
      academicLevelService.getLevels({ activeOnly: true }),
      academicLevelService.getCategories(),
    ])
      .then(([levelResponse, categoryResponse]) => {
        if (!active) return;
        setLevels(asItems(levelResponse));
        setCategories(asItems(categoryResponse));
      })
      .catch((error) => {
        if (active)
          showError(
            getErrorMessage(error, "Could not load automatic progression."),
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [showError]);

  const orderedCategories = useMemo(
    () => [...categories].sort((left, right) => left.position - right.position),
    [categories],
  );

  const categoryIndex = useMemo(
    () =>
      new Map(
        orderedCategories.map((category, index) => [category.value, index]),
      ),
    [orderedCategories],
  );

  const orderedLevels = useMemo(
    () =>
      [...levels].sort((left, right) => {
        const leftIndex =
          categoryIndex.get(left.category) ?? Number.MAX_SAFE_INTEGER;
        const rightIndex =
          categoryIndex.get(right.category) ?? Number.MAX_SAFE_INTEGER;
        return leftIndex - rightIndex || left.position - right.position;
      }),
    [categoryIndex, levels],
  );

  const progressionByLevel = useMemo(() => {
    const result = new Map();
    const levelsByCategory = new Map();
    orderedLevels.forEach((level) => {
      const rows = levelsByCategory.get(level.category) || [];
      rows.push(level);
      levelsByCategory.set(level.category, rows);
    });

    orderedLevels.forEach((level) => {
      const sameCategory = (levelsByCategory.get(level.category) || [])
        .filter((candidate) => candidate.position > level.position)
        .sort((left, right) => left.position - right.position);
      if (sameCategory.length) {
        result.set(level.id, { type: "next", level: sameCategory[0] });
        return;
      }

      const currentIndex = categoryIndex.get(level.category);
      if (currentIndex === undefined) {
        result.set(level.id, { type: "invalid" });
        return;
      }
      if (currentIndex === orderedCategories.length - 1) {
        result.set(level.id, { type: "terminal" });
        return;
      }

      const nextCategory = orderedCategories[currentIndex + 1];
      const nextCategoryLevels = (
        levelsByCategory.get(nextCategory.value) || []
      )
        .slice()
        .sort((left, right) => left.position - right.position);
      if (!nextCategoryLevels.length) {
        result.set(level.id, { type: "incomplete", category: nextCategory });
        return;
      }
      result.set(level.id, { type: "next", level: nextCategoryLevels[0] });
    });
    return result;
  }, [categoryIndex, orderedCategories, orderedLevels]);

  if (loading) return <LoadingState label="Loading automatic progression..." />;

  return (
    <WorkspacePanel
      title="Automatic level transitions"
      description="This is a read-only view. Institution category order and level position determine progression; class, arm, and department never affect it."
    >
      {orderedLevels.length ? (
        <div className="space-y-3">
          {orderedLevels.map((level) => {
            const progression = progressionByLevel.get(level.id);
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
                <ArrowRight
                  className="hidden h-5 w-5 text-text-faint sm:block"
                  aria-hidden="true"
                />
                {progression?.type === "next" ? (
                  <div>
                    <Badge variant="success">Next level</Badge>
                    <p className="mt-2 font-semibold text-text">
                      {progression.level.name}
                    </p>
                    <p className="mt-1 text-sm text-text-muted">
                      {categoryLabel(progression.level.category)} · Position{" "}
                      {progression.level.position}
                    </p>
                  </div>
                ) : progression?.type === "terminal" ? (
                  <div>
                    <Badge variant="primary">Completion</Badge>
                    <p className="mt-2 flex items-center gap-2 font-semibold text-text">
                      <GraduationCap className="h-4 w-4" aria-hidden="true" />
                      Graduate after explicit closure confirmation
                    </p>
                  </div>
                ) : progression?.type === "incomplete" ? (
                  <div>
                    <Badge variant="warning">Setup incomplete</Badge>
                    <p className="mt-2 flex items-center gap-2 font-semibold text-text">
                      <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                      Add a{" "}
                      {progression.category.label ||
                        categoryLabel(progression.category.value)}{" "}
                      level
                    </p>
                    <p className="mt-1 text-sm text-text-muted">
                      Weave will not skip a missing institution category or
                      treat it as graduation.
                    </p>
                  </div>
                ) : (
                  <div>
                    <Badge variant="error">Invalid configuration</Badge>
                    <p className="mt-2 text-sm text-text-muted">
                      This level uses a category that is not supported by the
                      current institution type.
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
