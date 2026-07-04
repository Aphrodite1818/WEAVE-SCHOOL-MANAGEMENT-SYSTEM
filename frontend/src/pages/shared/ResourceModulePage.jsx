import DashboardLayout from "../../components/layout/DashboardLayout";
import ResourcePage from "./ResourcePage";

function ResourceModulePage({
  role,
  title,
  description,
  config,
  actions,
  notice,
}) {
  return (
    <DashboardLayout role={role} title={title} description={description} actions={actions}>
      {notice}
      <ResourcePage config={config} />
    </DashboardLayout>
  );
}

export default ResourceModulePage;
