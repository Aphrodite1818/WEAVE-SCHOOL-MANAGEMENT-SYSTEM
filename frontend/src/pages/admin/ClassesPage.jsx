import { useMemo } from "react";
import ResourceModulePage from "../shared/ResourceModulePage";
import { getClassResourceConfig } from "../shared/resourceConfigs";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { formatUsageValue } from "../../features/subscriptions/subscriptionConfig";

function ClassesPage() {
  const { getResourceGuard } = useSubscription();
  const classGuard = getResourceGuard("classes", {
    featureCode: "academic_setup",
  });
  const config = useMemo(() => {
    const baseConfig = getClassResourceConfig({ role: "admin", writable: true });
    return {
      ...baseConfig,
      canCreate: baseConfig.canCreate && classGuard.allowed,
    };
  }, [classGuard.allowed]);

  return (
    <ResourceModulePage
      role="admin"
      title="Classes"
      description="Organize classes, arms, class teachers, and academic groupings."
      config={config}
      notice={
        !classGuard.allowed ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">
            {classGuard.reason} Current usage: {formatUsageValue(classGuard.usage)}.
          </div>
        ) : null
      }
    />
  );
}

export default ClassesPage;
