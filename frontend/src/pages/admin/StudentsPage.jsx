import DashboardLayout from "../../components/layout/DashboardLayout";
import StudentDirectoryPage from "./StudentDirectoryPage";

function StudentsPage() {
  return (
    <DashboardLayout role="admin">
      <StudentDirectoryPage />
    </DashboardLayout>
  );
}

export default StudentsPage;
