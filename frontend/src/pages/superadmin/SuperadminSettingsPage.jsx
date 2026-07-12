import { KeyRound, Shield, Users } from "lucide-react";
import { Link } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";

function SuperadminSettingsPage() {
  return (
    <DashboardLayout role="superadmin" title="Settings">
      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="p-4 sm:p-6">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-soft text-primary">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-text">Platform settings</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
                Keep durable platform configuration separate from incident response controls. Lockdown and IP containment now live in Control Center.
              </p>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <SettingsTile icon={Users} title="Superadmin access" description="Review platform owner accounts and invite trusted operators when needed." />
            <SettingsTile icon={KeyRound} title="Security boundaries" description="Superadmin actions stay global, tenant actions stay tenant-scoped." />
          </div>
        </Card>

        <Card className="p-4 sm:p-6">
          <h3 className="text-lg font-semibold text-text">Emergency controls moved</h3>
          <p className="mt-2 text-sm leading-6 text-text-muted">
            Platform lockdown is a central-control operation, not a preference. Open Control Center when you need to lock down traffic or manage IP blocks.
          </p>
          <Link to="/superadmin/control-center" className="mt-5 block">
            <Button className="w-full">
              <Shield className="h-4 w-4" />
              Open Control Center
            </Button>
          </Link>
        </Card>
      </section>
    </DashboardLayout>
  );
}

function SettingsTile({ icon: Icon, title, description }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-surface-muted/25 p-4">
      <Icon className="h-5 w-5 text-primary" />
      <h3 className="mt-3 text-sm font-semibold text-text">{title}</h3>
      <p className="mt-1 text-xs leading-5 text-text-muted">{description}</p>
    </div>
  );
}

export default SuperadminSettingsPage;
