import { Shield } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/shared/EmptyState";
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
      description="Terms, compliance notes, and school platform policy references can live here when they are ready."
    >
      <Card className="p-5 sm:p-6">
        <EmptyState
          icon={Shield}
          title="Legal information is not connected yet"
          description="This space is reserved for legal and policy information without exposing placeholder privacy-policy content."
        />
      </Card>
    </DashboardLayout>
  );
}

export default LegalPage;
