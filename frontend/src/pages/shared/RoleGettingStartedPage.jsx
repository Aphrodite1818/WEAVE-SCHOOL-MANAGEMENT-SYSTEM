import { Compass, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import { requestWorkspaceTour } from "../../features/guides/workspaceTourState";

export default function RoleGettingStartedPage({ role }) {
  const navigate = useNavigate();
  return <DashboardLayout role={role}>
    <section className="mx-auto my-8 max-w-xl rounded-2xl border border-border bg-surface p-8 sm:my-16 sm:p-12">
      <Compass className="h-9 w-9 text-primary" />
      <h1 className="mt-6 text-3xl font-semibold tracking-tight text-text">Find your way around.</h1>
      <p className="mt-4 text-base leading-7 text-text-muted">A short introduction to your school workspace. Follow the menu highlights to learn where everything belongs.</p>
      <div className="mt-8 flex flex-wrap gap-3"><Button onClick={() => requestWorkspaceTour(role)}>Show me around<ArrowRight className="h-4 w-4" /></Button><Button variant="ghost" onClick={() => navigate(`/${role}/dashboard`, { replace: true })}>Go to dashboard</Button></div>
    </section>
  </DashboardLayout>;
}
