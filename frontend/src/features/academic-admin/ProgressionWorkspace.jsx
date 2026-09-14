import { GraduationCap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import LoadingState from "../../components/shared/LoadingState";
import { useToast } from "../../hooks/useToast";
import { academicLevelService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { RecordList } from "./AcademicWorkspacePrimitives";

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
        if (active) {
          showError(
            getErrorMessage(error, "Could not load automatic progression."),
          );
        }
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

  const rows = useMemo(
    () =>
      orderedLevels.map((level) => ({
        ...level,
        progression: progressionByLevel.get(level.id),
      })),
    [orderedLevels, progressionByLevel],
  );

  if (loading) return <LoadingState label="Loading automatic progression..." />;

  return (
    <RecordList
      title="Automatic level transitions"
      description="This is a read-only view. Institution category order and level position determine progression; class, arm, and department never affect it."
      items={rows}
      emptyIcon={GraduationCap}
      emptyTitle="No progression path yet"
      emptyDescription="Create an academic level to preview progression."
      renderTitle={(item) => item.name}
      renderMeta={(item) =>
        `${categoryLabel(item.category)} · Position ${item.position}`
      }
      renderStatus={(item) => {
        if (item.progression?.type === "next") return "ready";
        if (item.progression?.type === "terminal") return "complete";
        if (item.progression?.type === "incomplete") return "pending";
        return "failed";
      }}
      renderDescription={(item) => {
        if (item.progression?.type === "next") {
          return `Next level: ${item.progression.level.name} · ${categoryLabel(
            item.progression.level.category,
          )} position ${item.progression.level.position}`;
        }
        if (item.progression?.type === "terminal") {
          return "Graduate after explicit closure confirmation.";
        }
        if (item.progression?.type === "incomplete") {
          return `Setup incomplete: add a ${
            item.progression.category.label ||
            categoryLabel(item.progression.category.value)
          } level. Weave will not skip a missing institution category or treat it as graduation.`;
        }
        return "Invalid configuration: this level uses a category that is not supported by the current institution type.";
      }}
    />
  );
}

export default ProgressionWorkspace;
