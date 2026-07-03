import { useEffect, useState } from "react";
import { CheckSquare } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import LoadingState from "../../components/shared/LoadingState";
import EmptyState from "../../components/shared/EmptyState";
import ResourceModulePage from "../shared/ResourceModulePage";
import { getAttendanceResourceConfig } from "../shared/resourceConfigs";
import { getErrorMessage } from "../../services/api";
import { classService } from "../../services/academicsService";

function AttendancePage() {
  const [classTeacherClasses, setClassTeacherClasses] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    async function loadClassTeacherClasses() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await classService.getClasses({ limit: 100, active_only: true });
        if (mounted) setClassTeacherClasses(response?.items || []);
      } catch (err) {
        if (mounted) setError(getErrorMessage(err, "Could not verify class-teacher assignment."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }
    loadClassTeacherClasses();
    return () => {
      mounted = false;
    };
  }, []);

  if (isLoading) {
    return (
      <DashboardLayout role="teacher" title="Class Attendance">
        <LoadingState label="Checking class-teacher access..." />
      </DashboardLayout>
    );
  }

  if (error || classTeacherClasses.length === 0) {
    return (
      <DashboardLayout
        role="teacher"
        title="Class Attendance"
        description="Attendance is a class-teacher duty, not a class-subject teacher duty."
      >
        {error ? <div className="rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">{error}</div> : null}
        <Card className="p-5 sm:p-6">
          <EmptyState
            icon={CheckSquare}
            title="Class-teacher access required"
            description="You are not assigned as the main teacher for any class, so attendance tools are not available on your dashboard. Subject teachers can still use Score Entry and Teaching Rosters."
          />
        </Card>
      </DashboardLayout>
    );
  }

  return (
    <ResourceModulePage
      role="teacher"
      title="Class Attendance"
      description="Mark attendance only for classes where you are the assigned class teacher."
      config={getAttendanceResourceConfig({ writable: true, canDelete: false, role: "teacher" })}
    />
  );
}

export default AttendancePage;
