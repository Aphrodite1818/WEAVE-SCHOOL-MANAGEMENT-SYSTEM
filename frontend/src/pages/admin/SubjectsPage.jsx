import { useMemo } from "react";
import ResourceModulePage from "../shared/ResourceModulePage";
import { subjectResourceConfig } from "../shared/resourceConfigs";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { formatUsageValue } from "../../features/subscriptions/subscriptionConfig";

function SubjectsPage() {
  const { getResourceGuard } = useSubscription();
  const subjectGuard = getResourceGuard("subjects", {
    featureCode: "academic_setup",
  });
  const config = useMemo(
    () => ({
      ...subjectResourceConfig,
      canCreate: subjectResourceConfig.canCreate && subjectGuard.allowed,
    }),
    [subjectGuard.allowed]
  );

  return (
    <ResourceModulePage
      role="admin"
      title="Subjects"
      description="Maintain the subject catalog used by classes, teachers, exams, and results."
      config={config}
      notice={
        !subjectGuard.allowed ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">
            {subjectGuard.reason} Current usage: {formatUsageValue(subjectGuard.usage)}.
          </div>
        ) : null
      }
    />
  );
}

export default SubjectsPage;
