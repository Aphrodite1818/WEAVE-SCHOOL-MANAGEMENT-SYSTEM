import { Link } from "react-router-dom";
import { Plus } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import StudentDirectoryPage from "./StudentDirectoryPage";

function StudentsPage() {
  return (
    <DashboardLayout
      role="admin"
      title="Student Directory"
      description="Search, filter, create, and maintain student records across classes."
      actions={
        <Link to="/admin/students/create">
          <Button
            type="button"
            variant="success"
            className="min-w-[10.5rem] justify-center rounded-lg"
          >
            <Plus className="h-4 w-4" />
            Create student
          </Button>
        </Link>
      }
    >
      <StudentDirectoryPage />
    </DashboardLayout>
  );
}

export default StudentsPage;
