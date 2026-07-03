import ResourceModulePage from "../shared/ResourceModulePage";
import { getClassResourceConfig } from "../shared/resourceConfigs";

function MyClassesPage() {
  return (
    <ResourceModulePage
      role="teacher"
      title="My Class Teacher Classes"
      description="View only the classes where you are assigned as the main class teacher. Subject-teaching classes are listed under Teaching Rosters."
      config={getClassResourceConfig({ role: "teacher", writable: false })}
    />
  );
}

export default MyClassesPage;
