import { Link } from "react-router-dom";

import Button from "../../components/ui/Button";
import ResourceModulePage from "../shared/ResourceModulePage";
import { subjectReadOnlyResourceConfig } from "../shared/resourceConfigs";

function SubjectsPage() {
  return (
    <ResourceModulePage
      role="admin"
      title="Subjects"
      description="View the subject catalog. Create or edit subjects from Academic Hub so academic setup stays centralized."
      config={subjectReadOnlyResourceConfig}
      actions={
        <Link to="/admin/academic/setup">
          <Button>Open Academic Hub</Button>
        </Link>
      }
      notice={
        <div className="rounded-2xl border border-primary/20 bg-primary-soft/60 px-4 py-3 text-sm font-medium text-primary">
          This page is view-only. Subject creation and editing now live in Academic Hub.
        </div>
      }
    />
  );
}

export default SubjectsPage;
