import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ArrowRight,
  Building2,
  GraduationCap,
  Menu,
  Users,
  X,
} from "lucide-react";
import WeaveIcon from "../brand/WeaveIcon";
import Button from "../ui/Button";

const signupOptions = [
  {
    title: "School administrator",
    shortTitle: "Create a school",
    description: "Create a new school workspace and begin the free trial.",
    to: "/register",
    icon: Building2,
  },
  {
    title: "Teacher",
    shortTitle: "Teacher sign up",
    description: "Create your teacher account, then accept your school invitation.",
    to: "/teacher/register",
    icon: GraduationCap,
  },
  {
    title: "Parent",
    shortTitle: "Parent sign up",
    description: "Create your parent account, then accept the invitation for your child.",
    to: "/parent/register",
    icon: Users,
  },
];

function Navbar() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const isLandingPage = location.pathname === "/";
  const links = [
    { label: "Home", href: "/#home" },
    { label: "Join", href: "/#join" },
    { label: "Features", href: "/#features" },
    { label: "Benefits", href: "/#benefits" },
    { label: "Pricing", to: "/pricing" },
  ];

  const renderNavLink = (link, className, onClick) => {
    if (link.to) {
      return (
        <Link key={link.to} to={link.to} onClick={onClick} className={className}>
          {link.label}
        </Link>
      );
    }

    if (link.href?.startsWith("/")) {
      return (
        <Link key={link.href} to={link.href} onClick={onClick} className={className}>
          {link.label}
        </Link>
      );
    }

    return (
      <a key={link.href} href={link.href} onClick={onClick} className={className}>
        {link.label}
      </a>
    );
  };

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-50 border-b border-border bg-background/92 pt-[max(0.35rem,env(safe-area-inset-top))] shadow-sm backdrop-blur-xl md:pt-0">
        <div className="section-container flex min-h-16 items-center justify-between gap-4 md:min-h-20">
          <Link to="/#home" className="flex items-center gap-2.5">
            <WeaveIcon className="-ml-1 h-14 w-14 shrink-0" />
            <div>
              <p className="text-base font-bold leading-tight">Weave</p>
              <p className="text-xs text-text-muted">School Management</p>
            </div>
          </Link>

          <nav className="hidden items-center gap-7 md:flex">
            {links.map((link) =>
              renderNavLink(link, "text-sm font-semibold text-text-soft hover:text-primary")
            )}
            <Link to="/login" className="text-sm font-semibold text-text-soft hover:text-primary">
              Log in
            </Link>
            <Link to="/register">
              <Button>Create school</Button>
            </Link>
          </nav>

          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setOpen((current) => !current)}
            aria-label="Toggle menu"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>

        {open && (
          <div className="border-t border-border bg-surface px-3 py-3 shadow-premium md:hidden">
            <nav className="grid gap-1.5 rounded-2xl border border-border/70 bg-surface-muted/35 p-1.5">
              {links.map((link) =>
                renderNavLink(
                  link,
                  "flex min-h-11 items-center rounded-xl px-3 text-sm font-semibold text-text-soft transition hover:bg-surface hover:text-primary",
                  () => setOpen(false),
                )
              )}
              <Link
                to="/login"
                onClick={() => setOpen(false)}
                className="flex min-h-11 items-center rounded-xl px-3 text-sm font-semibold text-text-soft transition hover:bg-surface hover:text-primary"
              >
                Log in
              </Link>

              <div className="mt-1 border-t border-border/70 pt-2">
                <p className="px-3 pb-1 text-[11px] font-bold uppercase tracking-wide text-text-muted">
                  Create an account
                </p>
                {signupOptions.map((option) => {
                  const Icon = option.icon;
                  return (
                    <Link
                      key={option.to}
                      to={option.to}
                      onClick={() => setOpen(false)}
                      className="flex min-h-12 items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold text-text-soft transition hover:bg-surface hover:text-primary"
                    >
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                        <Icon className="h-4 w-4" />
                      </span>
                      <span>{option.shortTitle}</span>
                    </Link>
                  );
                })}
              </div>
            </nav>
          </div>
        )}
      </header>

      <div
        className="h-[calc(4rem+max(0.35rem,env(safe-area-inset-top)))] md:h-20"
        aria-hidden="true"
      />

      {isLandingPage ? (
        <section id="join" className="scroll-mt-24 border-b border-border bg-surface">
          <div className="section-container py-5 sm:py-6">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-xl">
                <p className="text-xs font-bold uppercase tracking-wide text-primary">
                  Choose how you are joining
                </p>
                <h2 className="mt-2 text-xl font-semibold text-text sm:text-2xl">
                  Create the account that matches your role.
                </h2>
                <p className="mt-2 text-sm leading-6 text-text-muted">
                  School administrators create workspaces. Teachers and parents create global accounts that can connect to one or more invited schools.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[42rem]">
                {signupOptions.map((option) => {
                  const Icon = option.icon;
                  return (
                    <Link
                      key={option.to}
                      to={option.to}
                      className="group flex min-h-[9.5rem] flex-col rounded-2xl border border-border/70 bg-background p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-soft-card"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                          <Icon className="h-5 w-5" />
                        </span>
                        <ArrowRight className="h-4 w-4 text-text-faint transition group-hover:translate-x-0.5 group-hover:text-primary" />
                      </div>
                      <p className="mt-4 text-sm font-semibold text-text">{option.title}</p>
                      <p className="mt-1 text-xs leading-5 text-text-muted">{option.description}</p>
                    </Link>
                  );
                })}
              </div>
            </div>

            <p className="mt-4 rounded-xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-xs leading-5 text-text-muted">
              Students do not self-register. Their school provides an admission number and first-login access code; they should use the regular log-in page.
            </p>
          </div>
        </section>
      ) : null}
    </>
  );
}

export default Navbar;
