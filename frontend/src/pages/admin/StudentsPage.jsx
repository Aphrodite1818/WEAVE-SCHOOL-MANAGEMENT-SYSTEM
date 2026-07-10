import DashboardLayout from "../../components/layout/DashboardLayout";
import StudentDirectoryPage from "./StudentDirectoryPage";

function StudentsPage() {
  return (
    <DashboardLayout
      role="admin"
      title="Student Directory"
      description="Search, filter, create, and maintain student records across classes."
    >
      <StudentDirectoryPage />
    </DashboardLayout>
  );
}

export default StudentsPage;
