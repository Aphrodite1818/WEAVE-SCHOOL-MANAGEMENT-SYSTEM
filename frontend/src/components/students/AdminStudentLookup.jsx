import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";

import Button from "../ui/Button";
import Input from "../ui/Input";
import { getErrorMessage } from "../../services/api";
import { studentService } from "../../services/studentService";

const PAGE_SIZE = 20;

const normalizeAdmissionReference = (value) =>
  String(value || "")
    .replace(/[^a-z0-9]/gi, "")
    .toUpperCase();

const studentLabel = (student) => {
  const name = [student?.first_name, student?.last_name]
    .filter(Boolean)
    .join(" ")
    .trim();
  return `${name || "Student"} · ${student?.admission_number || "No admission number"}`;
};

export default function AdminStudentLookup({ value, onChange, error, disabled = false }) {
  const onChangeRef = useRef(onChange);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(async () => {
      setLoading(true);
      setLoadError("");
      try {
        const response = await studentService.getAdminStudents({
          skip: (page - 1) * PAGE_SIZE,
          limit: PAGE_SIZE,
          search: query.trim() || undefined,
          status: "active",
        });
        if (controller.signal.aborted) return;
        const nextItems = Array.isArray(response?.items) ? response.items : [];
        const normalizedQuery = normalizeAdmissionReference(query);
        const exactAdmissionMatch =
          normalizedQuery && nextItems.find(
            (student) =>
              normalizeAdmissionReference(student?.admission_number) === normalizedQuery,
          );

        setItems(nextItems);
        setTotal(Number(response?.total || 0));
        if (exactAdmissionMatch && exactAdmissionMatch.id !== value) {
          setSelectedRecord(exactAdmissionMatch);
          onChangeRef.current?.(exactAdmissionMatch.id, exactAdmissionMatch);
        }
      } catch (requestError) {
        if (controller.signal.aborted) return;
        setLoadError(
          getErrorMessage(requestError, "Could not search active students."),
        );
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, query ? 250 : 0);

    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [page, query, value]);

  const options = useMemo(() => {
    if (!selectedRecord || items.some((item) => item.id === selectedRecord.id)) {
      return items;
    }
    return [selectedRecord, ...items];
  }, [items, selectedRecord]);
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const selectedStudent =
    selectedRecord || options.find((item) => item.id === value) || null;

  const handleSelection = (event) => {
    const nextId = event.target.value;
    const record = options.find((item) => item.id === nextId) || null;
    setSelectedRecord(record);
    onChange(nextId, record);
  };

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <Input
          label="Find student"
          value={query}
          onChange={(event) => {
            const nextQuery = event.target.value;
            const selectedAdmission = normalizeAdmissionReference(
              selectedStudent?.admission_number,
            );
            setQuery(nextQuery);
            setPage(1);
            if (
              value &&
              selectedAdmission &&
              normalizeAdmissionReference(nextQuery) !== selectedAdmission
            ) {
              setSelectedRecord(null);
              onChange("", null);
            }
          }}
          placeholder="Search name or admission number"
          className="pl-11"
          disabled={disabled}
        />
      </div>

      <label className="block">
        <span className="mb-1.5 block text-sm font-semibold text-text-soft">
          Student
        </span>
        {selectedStudent ? (
          <div className="mb-2 rounded-xl border border-primary/25 bg-primary-subtle/50 px-3 py-2.5 text-sm font-semibold text-text">
            {studentLabel(selectedStudent)}
          </div>
        ) : null}
        <select
          value={value}
          onChange={handleSelection}
          className="input-base"
          required
          disabled={disabled || loading}
        >
          <option value="">
            {loading ? "Loading students..." : "Select active student"}
          </option>
          {options.map((student) => (
            <option key={student.id} value={student.id}>
              {studentLabel(student)}
            </option>
          ))}
        </select>
        {error ? <span className="mt-1 block text-xs text-error">{error}</span> : null}
        {loadError ? (
          <span className="mt-1 block text-xs text-error">{loadError}</span>
        ) : null}
      </label>

      <div className="flex items-center justify-between gap-3 text-xs text-text-muted">
        <span>{total} active student{total === 1 ? "" : "s"}</span>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label="Previous student page"
            disabled={disabled || loading || page <= 1}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span>
            {page}/{pageCount}
          </span>
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label="Next student page"
            disabled={disabled || loading || page >= pageCount}
            onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
