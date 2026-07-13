import { useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X } from "lucide-react";
import WeaveIcon from "../brand/WeaveIcon";
import Button from "../ui/Button";

function Navbar() {
  const [open, setOpen] = useState(false);
  const links = [
    { label: "Home", href: "/#home" },
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
      <header className="fixed inset-x-0 top-0 z-50 border-b border-border bg-background/92 shadow-sm backdrop-blur-xl">
        <div className="section-container flex min-h-20 items-center justify-between gap-4">
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
              <Button>Start free</Button>
            </Link>
          </nav>

          <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setOpen((current) => !current)} aria-label="Toggle menu">
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
              <Link to="/login" onClick={() => setOpen(false)} className="flex min-h-11 items-center rounded-xl px-3 text-sm font-semibold text-text-soft transition hover:bg-surface hover:text-primary">
                Log in
              </Link>
              <Link to="/register" onClick={() => setOpen(false)} className="mt-1">
                <Button className="w-full">Start free</Button>
              </Link>
            </nav>
          </div>
        )}
      </header>
      <div className="h-20" aria-hidden="true" />
    </>
  );
}

export default Navbar;
