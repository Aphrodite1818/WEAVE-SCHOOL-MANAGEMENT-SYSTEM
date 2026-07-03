import { useEffect, useRef, useState } from "react";
import { ChevronRight, Search, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { searchService } from "../../services/searchService";
import { cn } from "../../utils/cn";

const placeholderByRole = {
  admin: "Search students, teachers, parents, classes...",
  teacher: "Search my students, classes, subjects, results...",
  superadmin: "Search tenants, schools, admins...",
};

function WorkspaceSearch({ role }) {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [query, setQuery] = useState("");
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const trimmed = query.trim();

    if (trimmed.length < 2) {
      return undefined;
    }

    let active = true;
    const timeoutId = window.setTimeout(async () => {
      setIsLoading(true);
      setError("");
      setItems([]);

      try {
        const response = await searchService.searchWorkspace(role, trimmed, 8);
        if (!active) return;
        setItems(response?.items || []);
      } catch (err) {
        if (!active) return;
        setItems([]);
        setError(err?.message || "Search is temporarily unavailable.");
      } finally {
        if (active) setIsLoading(false);
      }
    }, 250);

    return () => {
      active = false;
      window.clearTimeout(timeoutId);
    };
  }, [query, role]);

  useEffect(() => {
    const handleShortcut = (event) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key !== "/") return;
      const target = event.target;
      const isTypingTarget =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        target?.isContentEditable;
      if (isTypingTarget) return;

      event.preventDefault();
      inputRef.current?.focus();
    };

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  const handleSelect = (href) => {
    setQuery("");
    setItems([]);
    setError("");
    navigate(href);
  };

  const handleQueryChange = (event) => {
    const nextQuery = event.target.value;
    setQuery(nextQuery);

    if (nextQuery.trim().length < 2) {
      setItems([]);
      setIsLoading(false);
      setError("");
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Escape") {
      setQuery("");
      setItems([]);
      setError("");
      return;
    }

    if (event.key === "Enter" && items.length > 0) {
      event.preventDefault();
      handleSelect(items[0].href);
    }
  };

  const trimmed = query.trim();
  const showResults = trimmed.length >= 2 && (isLoading || error || items.length > 0);

  return (
    <div className="relative hidden w-full max-w-lg md:block">
      <div className="flex items-center gap-3 rounded-2xl border border-border bg-surface px-3.5 py-2.5 shadow-sm">
        <Search className="h-4 w-4 shrink-0 text-text-faint" />
        <input
          ref={inputRef}
          type="search"
          aria-label="Search workspace"
          placeholder={placeholderByRole[role] || placeholderByRole.admin}
          value={query}
          onChange={handleQueryChange}
          onKeyDown={handleKeyDown}
          className="w-full bg-transparent text-sm text-text outline-none placeholder:text-text-faint"
        />
        <kbd className="rounded-md border border-border bg-surface-muted px-1.5 py-0.5 text-xs font-semibold text-text-faint">
          /
        </kbd>
      </div>

      {showResults && (
        <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-50 overflow-hidden rounded-2xl border border-border bg-surface shadow-premium">
          <div className="border-b border-border bg-surface-muted/40 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              {isLoading ? "Searching" : `${items.length} result${items.length === 1 ? "" : "s"}`}
            </p>
            {error ? <p className="mt-1 text-sm text-error">{error}</p> : null}
          </div>
          <div className="max-h-96 overflow-auto p-2">
            {isLoading ? (
              <div className="flex items-center gap-2 rounded-xl px-3 py-3 text-sm text-text-muted">
                <Loader2 className="h-4 w-4 animate-spin" />
                Searching workspace...
              </div>
            ) : items.length === 0 ? (
              <div className="rounded-xl px-3 py-3 text-sm text-text-muted">
                No matches found for "{trimmed}".
              </div>
            ) : (
              items.map((item) => (
                <button
                  key={`${item.role}-${item.href}-${item.label}`}
                  type="button"
                  onClick={() => handleSelect(item.href)}
                  className={cn(
                    "flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left transition hover:bg-surface-muted/70",
                    "focus:bg-surface-muted/70 focus:outline-none"
                  )}
                >
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-border bg-surface-muted text-text-muted">
                    <Search className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-text">{item.label}</span>
                    <span className="mt-0.5 block truncate text-xs text-text-muted">
                      {[item.role, item.metadata, item.email, item.admission_number, item.staff_id, item.class_name, item.subject_name]
                        .filter(Boolean)
                        .join(" | ")}
                    </span>
                  </span>
                  <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-text-faint" />
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default WorkspaceSearch;
