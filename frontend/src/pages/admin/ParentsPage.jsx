import { Link2 } from "lucide-react";
import { Link } from "react-router-dom";

import Button from "../../components/ui/Button";
import MembershipDirectoryPage from "./MembershipDirectoryPage";

function ParentsPage() {
  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Link to="/admin/parents/links">
          <Button type="button" variant="outline">
            <Link2 className="h-4 w-4" />
            Manage child links
          </Button>
        </Link>
      </div>
      <MembershipDirectoryPage role="parent" />
    </div>
  );
}

export default ParentsPage;
