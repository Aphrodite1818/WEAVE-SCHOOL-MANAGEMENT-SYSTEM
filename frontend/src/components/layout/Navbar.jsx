import { useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X } from "lucide-react";
import Button from "../ui/Button";
import logoImage from "../../assets/images/favicon.png";

function Navbar() {
  const [open, setOpen] = useState(false);
  const links = [
    { label: "Features", href: "#features" },
    { label: "Benefits", href: "#benefits" },
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

    return (
      <a key={link.href} href={link.href} onClick={onClick} className={className}>
        {link.label}
      </a>
    );
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-xl">
      <div className="section-container flex min-h-20 items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-3">
          <img src={logoImage} alt="Learnly AI" className="h-10 w-10 rounded-2xl border border-border bg-white p-1" />
          <div>
            <p className="text-base font-bold leading-tight">Learnly AI</p>
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
        <div className="border-t border-border bg-surface px-4 py-4 md:hidden">
          <nav className="grid gap-2">
            {links.map((link) =>
              renderNavLink(
                link,
                "rounded-xl px-3 py-2 text-sm font-semibold text-text-soft hover:bg-surface-muted hover:text-primary",
                () => setOpen(false),
              )
            )}
            <Link to="/login" onClick={() => setOpen(false)} className="rounded-xl px-3 py-2 text-sm font-semibold text-text-soft hover:bg-surface-muted hover:text-primary">
              Log in
            </Link>
            <Link to="/register" onClick={() => setOpen(false)} className="mt-2">
              <Button className="w-full">Start free</Button>
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}

export default Navbar;
