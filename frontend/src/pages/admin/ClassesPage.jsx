import { Link } from "react-router-dom";

import ResourceModulePage from "../shared/ResourceModulePage";
import { getClassResourceConfig } from "../shared/resourceConfigs";
import Button from "../../components/ui/Button";

function ClassesPage() {
  const config = getClassResourceConfig({ role: "admin", writable: false });

  return (
    <ResourceModulePage
      role="admin"
      title="Classes"
      description="View classes and arms. Create or edit classes from Academic Hub so setup stays in one place."
      config={config}
      actions={
        <Link to="/admin/academic/class-subjects">
          <Button>Open Academic Hub</Button>
        </Link>
      }
      notice={
        <div className="rounded-2xl border border-primary/20 bg-primary-soft/60 px-4 py-3 text-sm font-medium text-primary">
          This page is view-only. Class creation, editing, and subject attachment now live in Academic Hub.
        </div>
      }
    />
  );
}

export default ClassesPage;
