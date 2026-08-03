import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckSquare,
  Eye,
  KeyRound,
  Loader2,
  Printer,
  Search,
  Users,
  X,
} from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Modal from "../../components/ui/Modal";
import {
  createStudentSlipPrintWindow,
  renderStudentSlipPrintDocument,
} from "../../features/bulkImports/studentSlips/printStudentSlips";
import { useToast } from "../../hooks/useToast";
import { getErrorMessage } from "../../services/api";
import { bulkImportService } from "../../services/bulkImport.service";

const PAGE_SIZE = 50;

const formatDate = (value) => {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

function SummaryMetric({ label, value, icon: Icon, tone = "default" }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">{label}</p>
          <p className={[
            "mt-2 text-2xl font-bold",
            tone === "success" ? "text-success" : tone === "warning" ? "text-warning" : "text-text",
          ].join(" ")}
          >
            {value ?? 0}
          </p>
        </div>
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </span>
      </div>
    </Card>
  );
}

function SlipPreview({ slip }) {
  return (
    <article className="overflow-hidden rounded-2xl border border-border bg-surface">
      <header className="flex items-start justify-between gap-3 border-b border-border bg-primary/5 p-4">
        <div className="flex min-w-0 items-center gap-3">
          {slip.school_logo_url ? (
            <img src={slip.school_logo_url} alt="" className="h-11 w-11 rounded-xl object-contain" />
          ) : (
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-primary font-bold text-text-inverse">W</span>
          )}
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-text">{slip.school_name}</p>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">Student login credentials</p>
          </div>
        </div>
        <Badge variant="info">Initial setup</Badge>
      </header>
      <dl className="divide-y divide-border p-4 text-sm">
        {[
          ["Student", slip.full_name],
          ["Class", slip.class_name],
          ["Admission number", slip.admission_number],
          ["Temporary access code", slip.setup_code],
          ["Login address", slip.login_url],
          ["Code expires", formatDate(slip.access_code_expires_at)],
        ].map(([label, value]) => (
          <div key={label} className="grid gap-1 py-3 sm:grid-cols-[160px_1fr] sm:gap-4">
            <dt className="font-semibold text-text-muted">{label}</dt>
            <dd className={[
              "m-0 break-words font-semibold text-text",
              label === "Temporary access code" ? "font-mono text-lg tracking-wider text-primary" : "",
            ].join(" ")}
            >
              {value || "--"}
            </dd>
          </div>
        ))}
      </dl>
      <div className="border-t border-border bg-warning/10 p-4 text-sm text-text-muted">
        Give this slip only to the student or their guardian. The student must create a new password after the first login.
      </div>
    </article>
  );
}

function StudentSlipsPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const { showError, showSuccess } = useToast();

  const [summary, setSummary] = useState(null);
  const [result, setResult] = useState({ items: [], total: 0, page: 1, total_pages: 0 });
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [classKey, setClassKey] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(() => new Set());
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [listLoading, setListLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [printIntent, setPrintIntent] = useState(null);
  const [layout, setLayout] = useState("two");

  const loadSummary = useCallback(async () => {
    const data = await bulkImportService.getSlipSummary(jobId);
    setSummary(data);
    return data;
  }, [jobId]);

  const loadList = useCallback(async () => {
    setListLoading(true);
    try {
      const data = await bulkImportService.listSlips(jobId, {
        search: debouncedSearch,
        classKey,
        page,
        pageSize: PAGE_SIZE,
      });
      setResult(data);
    } finally {
      setListLoading(false);
    }
  }, [classKey, debouncedSearch, jobId, page]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let mounted = true;
    Promise.all([loadSummary(), loadList()])
      .catch((error) => {
        if (mounted) showError(getErrorMessage(error, "Could not load student slips."));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [loadList, loadSummary, showError]);

  const pageRows = result.items || [];
  const selectablePageRows = pageRows.filter((item) => item.setup_code_available);
  const allPageSelected = selectablePageRows.length > 0
    && selectablePageRows.every((item) => selected.has(item.row_number));

  const selectedCount = selected.size;
  const selectedRows = useMemo(() => [...selected].sort((a, b) => a - b), [selected]);

  const toggleSelected = (rowNumber) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(rowNumber)) next.delete(rowNumber);
      else next.add(rowNumber);
      return next;
    });
  };

  const togglePage = () => {
    setSelected((current) => {
      const next = new Set(current);
      selectablePageRows.forEach((item) => {
        if (allPageSelected) next.delete(item.row_number);
        else next.add(item.row_number);
      });
      return next;
    });
  };

  const openPreview = async (rowNumber) => {
    setBusy(`preview-${rowNumber}`);
    try {
      setPreview(await bulkImportService.getSlip(jobId, rowNumber));
    } catch (error) {
      showError(getErrorMessage(error, "Could not open this student slip."));
    } finally {
      setBusy("");
    }
  };

  const executePrint = async (intent) => {
    let printWindow;
    try {
      printWindow = createStudentSlipPrintWindow();
    } catch (error) {
      showError(error.message);
      return;
    }

    setBusy(`print-${intent.mode}`);
    try {
      const data = await bulkImportService.getSlipPrintData(jobId, {
        mode: intent.mode,
        row_numbers: intent.mode === "selected" ? intent.rowNumbers : [],
        search: intent.mode === "filtered" ? debouncedSearch || null : null,
        class_key: intent.mode === "filtered" ? classKey || null : null,
      });
      renderStudentSlipPrintDocument(printWindow, data, { layout });
      if (data.unavailable_row_numbers?.length) {
        showError(`${data.unavailable_row_numbers.length} expired slip${data.unavailable_row_numbers.length === 1 ? " was" : "s were"} omitted from printing.`);
      } else {
        showSuccess(`${data.total} student slip${data.total === 1 ? "" : "s"} prepared for printing.`);
      }
    } catch (error) {
      printWindow.close();
      showError(getErrorMessage(error, "Could not prepare student slips for printing."));
    } finally {
      setBusy("");
      setPrintIntent(null);
    }
  };

  const requestPrint = (intent) => {
    const count = intent.mode === "selected"
      ? intent.rowNumbers.length
      : intent.mode === "filtered"
        ? result.total
        : summary?.printable_slips || 0;
    setPrintIntent({ ...intent, count });
  };

  const resetFilters = () => {
    setSearch("");
    setDebouncedSearch("");
    setClassKey("");
    setPage(1);
  };

  if (loading) {
    return (
      <DashboardLayout role="admin" title="Student Access Slips" description="Search and print credentials created by this bulk import.">
        <LoadingState label="Loading student slips..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="admin"
      title="Student Access Slips"
      description="Search, preview and print credentials created by this bulk import job."
      actions={(
        <Button variant="outline" onClick={() => navigate(`/admin/imports/process/${jobId}`)}>
          <ArrowLeft className="h-4 w-4" /> Back to import result
        </Button>
      )}
    >
      <div className="space-y-5">
        <Card className="border-warning/40 bg-warning/10 p-4">
          <div className="flex gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
            <div>
              <p className="font-semibold text-text">These slips contain temporary student credentials.</p>
              <p className="mt-1 text-sm text-text-muted">
                Print and distribute them securely. Codes become unavailable after their retention or access-code deadline.
                {summary?.credentials_available_until ? ` Latest stored credential deadline: ${formatDate(summary.credentials_available_until)}.` : ""}
              </p>
            </div>
          </div>
        </Card>

        <div className="grid gap-3 sm:grid-cols-3">
          <SummaryMetric label="Created slips" value={summary?.total_slips} icon={Users} />
          <SummaryMetric label="Printable now" value={summary?.printable_slips} icon={KeyRound} tone="success" />
          <SummaryMetric label="Unavailable" value={summary?.unavailable_slips} icon={AlertTriangle} tone="warning" />
        </div>

        <Card className="p-4 sm:p-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="grid flex-1 gap-3 md:grid-cols-[minmax(260px,1fr)_260px]">
              <label className="block">
                <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-text-muted">Search students</span>
                <span className="relative block">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    className="input-base w-full pl-9"
                    placeholder="Name or admission number"
                  />
                </span>
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-text-muted">Class</span>
                <select
                  value={classKey}
                  onChange={(event) => {
                    setClassKey(event.target.value);
                    setPage(1);
                  }}
                  className="input-base w-full"
                >
                  <option value="">All classes</option>
                  {(summary?.classes || []).map((item) => (
                    <option key={item.class_key} value={item.class_key}>
                      {item.class_name} — {item.count}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select value={layout} onChange={(event) => setLayout(event.target.value)} className="input-base w-auto" aria-label="Print layout">
                <option value="two">Two slips per page</option>
                <option value="one">One slip per page</option>
              </select>
              <Button variant="outline" onClick={resetFilters} disabled={!search && !classKey}>
                <X className="h-4 w-4" /> Clear filters
              </Button>
            </div>
          </div>

          <div className="mt-4 flex flex-col gap-3 border-t border-border pt-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-2 text-sm text-text-muted">
              <span>{result.total} matching student{result.total === 1 ? "" : "s"}</span>
              <span>·</span>
              <span>{selectedCount} selected</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => requestPrint({ mode: "selected", rowNumbers: selectedRows })} disabled={!selectedCount || Boolean(busy)}>
                <CheckSquare className="h-4 w-4" /> Print selected ({selectedCount})
              </Button>
              <Button variant="outline" onClick={() => requestPrint({ mode: "filtered", rowNumbers: [] })} disabled={!result.total || Boolean(busy)}>
                <Printer className="h-4 w-4" /> Print filtered ({result.total})
              </Button>
              <Button onClick={() => requestPrint({ mode: "all", rowNumbers: [] })} disabled={!summary?.printable_slips || Boolean(busy)}>
                <Printer className="h-4 w-4" /> Print all ({summary?.printable_slips || 0})
              </Button>
            </div>
          </div>
        </Card>

        <Card className="overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-border p-4">
            <div>
              <h2 className="font-semibold text-text">Imported students</h2>
              <p className="mt-1 text-sm text-text-muted">Only students successfully created by this import job appear here.</p>
            </div>
            {listLoading && <Loader2 className="h-5 w-5 animate-spin text-primary" />}
          </div>

          {!listLoading && pageRows.length === 0 ? (
            <div className="p-5">
              <EmptyState title="No matching student slips" description="Change the class filter or search text and try again." />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-[820px] w-full text-left text-sm">
                <thead className="border-b border-border bg-surface-muted/50 text-xs uppercase text-text-muted">
                  <tr>
                    <th className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={allPageSelected}
                        onChange={togglePage}
                        disabled={!selectablePageRows.length}
                        aria-label="Select all printable students on this page"
                      />
                    </th>
                    <th className="px-4 py-3">Student</th>
                    <th className="px-4 py-3">Admission number</th>
                    <th className="px-4 py-3">Class</th>
                    <th className="px-4 py-3">Credential</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {pageRows.map((item) => (
                    <tr key={item.row_number} className="hover:bg-surface-muted/30">
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selected.has(item.row_number)}
                          onChange={() => toggleSelected(item.row_number)}
                          disabled={!item.setup_code_available}
                          aria-label={`Select ${item.full_name}`}
                        />
                      </td>
                      <td className="px-4 py-3 font-semibold text-text">{item.full_name}</td>
                      <td className="px-4 py-3 font-mono text-xs text-text">{item.admission_number}</td>
                      <td className="px-4 py-3 text-text-muted">{item.class_name}</td>
                      <td className="px-4 py-3">
                        <Badge variant={item.setup_code_available ? "success" : "warning"}>
                          {item.setup_code_available ? "Available" : "Expired"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" size="sm" onClick={() => openPreview(item.row_number)} disabled={!item.setup_code_available || Boolean(busy)}>
                            {busy === `preview-${item.row_number}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}
                            Preview
                          </Button>
                          <Button size="sm" onClick={() => requestPrint({ mode: "selected", rowNumbers: [item.row_number] })} disabled={!item.setup_code_available || Boolean(busy)}>
                            <Printer className="h-4 w-4" /> Print
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex flex-col gap-3 border-t border-border p-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-text-muted">
              Page {result.page || 1} of {Math.max(result.total_pages || 0, 1)} · {result.total} result{result.total === 1 ? "" : "s"}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1 || listLoading} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</Button>
              <Button variant="outline" size="sm" disabled={page >= (result.total_pages || 1) || listLoading} onClick={() => setPage((value) => value + 1)}>Next</Button>
            </div>
          </div>
        </Card>
      </div>

      <Modal
        open={Boolean(preview)}
        title="Student access slip"
        description="Review the credential before printing."
        onClose={() => setPreview(null)}
        footer={preview ? (
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="outline" onClick={() => setPreview(null)}>Close</Button>
            <Button onClick={() => requestPrint({ mode: "selected", rowNumbers: [preview.row_number] })} disabled={Boolean(busy)}>
              <Printer className="h-4 w-4" /> Print this slip
            </Button>
          </div>
        ) : null}
      >
        {preview && <SlipPreview slip={preview} />}
      </Modal>

      <Modal
        open={Boolean(printIntent)}
        title={printIntent?.mode === "all" ? "Print every available slip?" : `Print ${printIntent?.count || 0} student slips?`}
        description={printIntent?.mode === "all" ? "Large print jobs may take time. Printing one class at a time is usually easier to distribute." : "The browser print window will contain only the selected scope."}
        onClose={() => setPrintIntent(null)}
        footer={(
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="outline" onClick={() => setPrintIntent(null)} disabled={Boolean(busy)}>Cancel</Button>
            <Button onClick={() => executePrint(printIntent)} disabled={Boolean(busy)}>
              {busy.startsWith("print-") ? <Loader2 className="h-4 w-4 animate-spin" /> : <Printer className="h-4 w-4" />}
              Prepare {printIntent?.count || 0} slips
            </Button>
          </div>
        )}
      >
        <div className="space-y-2 text-sm text-text-muted">
          <p>Layout: <strong className="text-text">{layout === "one" ? "One slip per page" : "Two slips per page"}</strong></p>
          <p>Expired credentials will be omitted and reported after the print data is prepared.</p>
        </div>
      </Modal>
    </DashboardLayout>
  );
}

export default StudentSlipsPage;
