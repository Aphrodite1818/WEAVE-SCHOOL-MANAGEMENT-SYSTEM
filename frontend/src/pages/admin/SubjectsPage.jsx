import { Link } from "react-router-dom";

import Button from "../../components/ui/Button";
import ResourceModulePage from "../shared/ResourceModulePage";
import { subjectReadOnlyResourceConfig } from "../shared/resourceConfigs";

function SubjectsPage() {
  return (
    <ResourceModulePage
      role="admin"
      title="Subjects"
      description="View the subject catalog. Create or edit subjects from the Subjects workspace."
      config={subjectReadOnlyResourceConfig}
      actions={
        <Link to="/admin/academic/subjects">
          <Button>Open Subjects</Button>
        </Link>
      }
      notice={
        <div className="rounded-2xl border border-primary/20 bg-primary-soft/60 px-4 py-3 text-sm font-medium text-primary">
          This page is view-only. Subject creation and editing now live in the Subjects workspace.
        </div>
      }
    />
  );
}

export default SubjectsPage;
