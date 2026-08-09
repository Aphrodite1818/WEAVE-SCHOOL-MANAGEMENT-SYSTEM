import { useEffect } from "react";
import WeaveIcon from "../brand/WeaveIcon";
import Spinner from "../ui/Spinner";

const BOOTSTRAP_BACKGROUND =
  "radial-gradient(circle at top left, rgba(37,99,235,0.16), transparent 26%), linear-gradient(180deg, #0b1220, #0f172a)";

function SessionBootstrapScreen() {
  useEffect(() => {
    const previousHtmlBackground = document.documentElement.style.background;
    const previousHtmlBackgroundColor = document.documentElement.style.backgroundColor;
    const previousBodyBackground = document.body.style.background;
    const previousBodyBackgroundColor = document.body.style.backgroundColor;
    const themeColorMeta = document.querySelector('meta[name="theme-color"]');
    const previousThemeColor = themeColorMeta?.getAttribute("content");

    document.documentElement.style.background = BOOTSTRAP_BACKGROUND;
    document.documentElement.style.backgroundColor = "#0f172a";
    document.body.style.background = BOOTSTRAP_BACKGROUND;
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
    <main className="auth-surface flex min-h-[100dvh] items-center justify-center bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.16),transparent_26%),linear-gradient(180deg,#0b1220,#0f172a)] px-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1.5rem,env(safe-area-inset-top))] text-white sm:px-8 lg:px-12">
      <div className="flex w-full max-w-md flex-col items-center text-center">
        <div className="flex items-center gap-3">
          <WeaveIcon className="h-12 w-12 shrink-0 sm:h-14 sm:w-14" />
          <div className="text-left">
            <p className="text-xl font-bold tracking-tight text-white sm:text-2xl">Weave</p>
            <p className="text-sm font-medium text-slate-400">School Management</p>
          </div>
        </div>

        <div className="mt-12 flex flex-col items-center sm:mt-14">
          <Spinner className="h-8 w-8" />
          <p className="mt-5 text-sm font-medium text-slate-300" aria-live="polite">
            Restoring your session…
          </p>
        </div>
      </div>
    </main>
  );
}

export default SessionBootstrapScreen;
