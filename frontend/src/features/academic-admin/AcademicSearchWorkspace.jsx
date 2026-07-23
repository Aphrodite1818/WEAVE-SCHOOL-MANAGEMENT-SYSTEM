import { ArrowRight, FileSearch, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import { getErrorMessage } from "../../services/api";
import { searchService } from "../../services/searchService";
import { WorkspacePanel } from "./AcademicWorkspacePrimitives";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

function AcademicSearchWorkspace() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const normalized = query.trim();
    if (normalized.length < 2) {
      setResults([]);
      setError(null);
      return undefined;
    }

    let mounted = true;
    const timeoutId = window.setTimeout(async () => {
      setIsSearching(true);
      setError(null);
      try {
        const response = await searchService.searchTenant(normalized, 30);
        if (mounted) setResults(asItems(response));
      } catch (err) {
        if (mounted) {
          setResults([]);
          setError(getErrorMessage(err, "Could not search academic records."));
        }
      } finally {
        if (mounted) setIsSearching(false);
      }
    }, 300);

    return () => {
      mounted = false;
      window.clearTimeout(timeoutId);
    };
  }, [query]);

  return (
    <WorkspacePanel
      title="Search academic records"
      description="Search across students, classes, subjects, report cards, and academic records."
    >
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by student, admission number, class, subject, or report card"
          className="pl-11"
        />
      </div>

      {error ? (
        <div className="mt-4 rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">
          {error}
        </div>
      ) : null}

      <div className="mt-5">
        {isSearching ? (
          <div className="flex min-h-28 items-center justify-center gap-2 rounded-2xl border border-border/70 bg-surface-muted/20 text-sm text-text-muted">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary/20 border-t-primary" />
            Searching...
          </div>
        ) : query.trim().length < 2 ? (
          <div className="rounded-2xl border border-dashed border-border p-8 text-center">
            <FileSearch className="mx-auto h-8 w-8 text-text-muted" />
            <p className="mt-3 text-sm font-semibold text-text">Enter at least two characters</p>
            <p className="mt-1 text-sm text-text-muted">
              Results appear automatically as you type.
            </p>
          </div>
        ) : results.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border p-8 text-center">
            <FileSearch className="mx-auto h-8 w-8 text-text-muted" />
            <p className="mt-3 text-sm font-semibold text-text">No matching records</p>
            <p className="mt-1 text-sm text-text-muted">
              Try a name, admission number, class, subject, or broader phrase.
            </p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {results.map((item, index) => {
              const key = item.result_key || item.key || item.id || `${item.type}-${index}`;
              const title = item.title || item.name || item.label || "Academic record";
              const description =
                item.description || item.subtitle || item.admission_number || item.email || "";
              const type = item.type || item.result_type || "record";
              const detailPath = item.result_key
                ? `/admin/search/${encodeURIComponent(item.result_key)}`
                : null;

              return (
                <div
                  key={key}
                  className="flex min-h-[10rem] flex-col rounded-2xl border border-border/70 bg-surface px-4 py-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="break-words font-semibold text-text">{title}</p>
                      {description ? (
                        <p className="mt-1 break-words text-sm leading-6 text-text-muted">
                          {description}
                        </p>
                      ) : null}
                    </div>
                    <Badge variant="default">{String(type).replaceAll("_", " ")}</Badge>
                  </div>
                  {detailPath ? (
                    <Link to={detailPath} className="mt-auto pt-4">
                      <Button type="button" size="small" variant="outline">
                        Open record
                        <ArrowRight className="h-4 w-4" />
                      </Button>
                    </Link>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </WorkspacePanel>
  );
}

export default AcademicSearchWorkspace;
