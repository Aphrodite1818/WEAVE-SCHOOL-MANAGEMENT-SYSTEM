import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import LegalComplianceContent from "../../features/legal/LegalComplianceContent";
import { authSession } from "../../services/api";

function normalizeRole(role) {
  const value = String(role || "").toLowerCase();
  if (["admin", "teacher", "student", "parent", "superadmin"].includes(value)) {
    return value;
  }
  return "admin";
}

function LegalPage() {
  const role = normalizeRole(authSession.getRole());

  return (
    <DashboardLayout
      role={role}
      title="Legal"
      description="Weave legal, data handling, and compliance terms."
    >
      <Card className="p-5 sm:p-6">
        <LegalComplianceContent role={role} />
      </Card>
    </DashboardLayout>
  );
}

export default LegalPage;
