import { Link } from "react-router-dom";
import { useEffect } from "react";
import { CheckCircle2, ShieldCheck } from "lucide-react";
import WeaveIcon from "../brand/WeaveIcon";
import Card from "../ui/Card";

const AUTH_BACKGROUND =
  "radial-gradient(circle at top left, rgba(37,99,235,0.16), transparent 26%), linear-gradient(180deg, #0b1220, #0f172a)";

function AuthLayout({
  title,
  description,
  children,
  footer,
  stepLabel = "",
  iconPosition = "header",
}) {
  useEffect(() => {
    const previousHtmlBackground = document.documentElement.style.background;
    const previousHtmlBackgroundColor = document.documentElement.style.backgroundColor;
    const previousBodyBackground = document.body.style.background;
    const previousBodyBackgroundColor = document.body.style.backgroundColor;
    const themeColorMeta = document.querySelector('meta[name="theme-color"]');
    const previousThemeColor = themeColorMeta?.getAttribute("content");

    document.documentElement.style.background = AUTH_BACKGROUND;
    document.documentElement.style.backgroundColor = "#0f172a";
    document.body.style.background = AUTH_BACKGROUND;
    document.body.style.backgroundColor = "#0f172a";
    themeColorMeta?.setAttribute("content", "#0f172a");

    return () => {
      document.documentElement.style.background = previousHtmlBackground;
      document.documentElement.style.backgroundColor = previousHtmlBackgroundColor;
      document.body.style.background = previousBodyBackground;
      document.body.style.backgroundColor = previousBodyBackgroundColor;
      if (previousThemeColor) themeColorMeta?.setAttribute("content", previousThemeColor);
    };
  }, []);

  return (
    <div className="auth-surface flex min-h-[100dvh] flex-col bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.16),transparent_26%),linear-gradient(180deg,#0b1220,#0f172a)] px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))] text-text sm:px-6 lg:grid lg:grid-cols-[minmax(0,0.92fr)_minmax(440px,0.68fr)] lg:px-0 lg:py-0">
      <section className="hidden border-r border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.12),transparent_34%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(15,23,42,0.92))] lg:flex lg:flex-col lg:justify-between lg:px-12 lg:py-10">
        <Link to="/" className="flex items-center gap-3">
          <WeaveIcon className="h-12 w-12 shrink-0" />
          <div>
            <p className="text-lg font-bold text-white">Weave</p>
            <p className="text-xs font-medium text-slate-400">School Management</p>
          </div>
        </Link>

        <div className="max-w-xl">
          <h1 className="text-5xl font-semibold leading-tight tracking-tight text-white">
            Calm, secure access for every school role.
          </h1>
          <p className="mt-5 max-w-lg text-base leading-7 text-slate-300">
            One workspace for administrators, teachers, parents, and learners to manage daily school operations.
          </p>
        </div>

        <div className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-4 backdrop-blur-xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Built for real school workflows
          </p>
          <div className="mt-4 grid gap-3">
            {[
              "Role-based access that stays tenant-aware.",
              "Authentication screens that work well on desktop and mobile.",
              "A cleaner front door for admins, teachers, parents, and students.",
            ].map((item) => (
              <div key={item} className="flex items-start gap-3 rounded-2xl border border-white/[0.08] bg-slate-950/35 px-4 py-3 text-sm font-medium text-slate-200">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      <main className="flex flex-1 items-center justify-center py-4 sm:py-5 lg:min-h-screen lg:px-8 lg:py-10">
        <div className="w-full max-w-md">
          <Link to="/" className="mb-7 flex items-center justify-center gap-3 lg:hidden">
            <WeaveIcon className="h-11 w-11 shrink-0" />
            <div>
              <p className="font-bold text-white">Weave</p>
              <p className="text-xs text-slate-400">School Management</p>
            </div>
          </Link>

          <Card className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-6 shadow-[0_24px_80px_rgba(2,6,23,0.45)] backdrop-blur-2xl sm:p-8">
            <div className="mb-7">
              {iconPosition === "header" ? (
                <span className="flex h-10 w-10 items-center justify-center rounded-[1rem] bg-white/10 text-slate-100">
                  <ShieldCheck className="h-4 w-4" />
                </span>
              ) : null}
              {stepLabel ? (
                <p className="mt-4 text-xs font-bold uppercase tracking-wide text-primary">
                  {stepLabel}
                </p>
              ) : null}
              <h1 className={`${iconPosition === "header" ? "mt-4" : ""} text-2xl font-semibold text-white`}>{title}</h1>
              {description && (
                <p className="mt-2 text-sm leading-6 text-slate-300">{description}</p>
              )}
            </div>
            {children}
            {footer}
          </Card>
          {iconPosition === "below" ? (
            <div className="mt-5 flex justify-center">
              <span className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-slate-100 shadow-[0_18px_45px_rgba(2,6,23,0.28)] backdrop-blur-xl">
                <ShieldCheck className="h-4 w-4" />
              </span>
            </div>
          ) : null}
        </div>
      </main>
    </div>
  );
}

export default AuthLayout;
