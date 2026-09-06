import { useCallback, useEffect, useRef, useState } from "react";
import Button from "../../components/ui/Button";
import { academicService } from "../../services/academicService";
import { curriculumService } from "../../services/curriculumService";
import { getErrorMessage } from "../../services/api";
import { SelectControl, WorkspacePanel } from "./AcademicWorkspacePrimitives";

export default function ClassSpecializationWorkspace({ levels, availability }) {
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [sessionId, setSessionId] = useState("");
  const [termId, setTermId] = useState("");
  const [levelId, setLevelId] = useState("");
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState([]);
  const [departmentId, setDepartmentId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [contextError, setContextError] = useState("");
  const [contextAttempt, setContextAttempt] = useState(0);
  const lock = useRef(false);
  const generation = useRef(0);
  useEffect(() => {
    let active = true;
    setContextError("");
    setLoading(true);
    Promise.all([academicService.listSessions({ limit: 100 }), academicService.listTerms({ limit: 100 })]).then(([sessionResult, termResult]) => {
      if (!active) return;
      const sessionRows = sessionResult?.items || sessionResult || [];
      const termRows = termResult?.items || termResult || [];
      setSessions(sessionRows);
      setTerms(termRows);
      const current = termRows.find((row) => row.is_current) || termRows[0];
      setSessionId(current?.academic_session_id || sessionRows[0]?.id || "");
      setTermId(current?.id || "");
      setLoading(false);
    }).catch((err) => {
      if (active) {
        setContextError(getErrorMessage(err, "Could not load sessions and terms."));
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [contextAttempt]);
  const load = useCallback(async () => {
    const request = ++generation.current;
    setRows([]);
    setError("");
    if (!termId) { setLoading(false); return; }
    setLoading(true);
    try {
      const response = await curriculumService.getSpecializationWorkspace(termId);
      if (request === generation.current) setRows(response.classes || []);
    } catch (err) {
      if (request === generation.current) setError(getErrorMessage(err, "Could not load exact-term specialization."));
    } finally { if (request === generation.current) setLoading(false); }
  }, [termId]);
  useEffect(() => { load(); return () => { generation.current += 1; }; }, [load]);
  useEffect(() => { setSelected([]); setDepartmentId(""); setFeedback(""); }, [termId, levelId]);
  const term = terms.find((row) => row.id === termId);
  const specializationLevelIds = new Set(levels.map((row) => row.id));
  const visible = rows.filter(
    (row) =>
      specializationLevelIds.has(row.academic_level_id) &&
      (!levelId || row.academic_level_id === levelId),
  );
  const editable = ["draft", "open"].includes(String(term?.status).toLowerCase());
  const optionsFor = (id) => (availability[String(id)] || []).filter((row) => row.is_active && !row.archived_at).map((row) => ({ value: row.id, label: row.department_name }));
  // Term names order the copy choices even before draft dates are configured.
  // Eligibility and whether copying is allowed are still validated by the backend.
  const termNames = ["first_term", "second_term", "third_term"];
  const sourceTerms = terms.filter((row) =>
    row.academic_session_id === sessionId &&
    termNames.indexOf(row.name) >= 0 &&
    termNames.indexOf(row.name) < termNames.indexOf(term?.name),
  );
  const assign = async (classIds, linkId) => {
    if (lock.current || !linkId || !classIds.length || !editable) return;
    lock.current = true; setPending(true); setError(""); setFeedback("");
    let completed = 0;
    const failures = [];
    const failedIds = [];
    try {
      // Existing per-class API commits independently; report every failure explicitly.
      for (const id of classIds) {
        try { await curriculumService.setClassDepartment(id, termId, linkId); completed += 1; }
        catch (err) {
          failedIds.push(id);
          failures.push(`${rows.find((row) => row.class_id === id)?.display_name}: ${getErrorMessage(err, "Assignment failed")}`);
        }
      }
      await load();
      setSelected(failedIds);
      setFeedback(`${completed} of ${classIds.length} class specializations saved.`);
      if (failures.length) setError(failures.join("\n"));
    } finally { lock.current = false; setPending(false); }
  };
  const copy = async () => {
    if (lock.current || String(term?.status).toLowerCase() !== "draft" || !sourceId) return;
    lock.current = true; setPending(true); setError("");
    try {
      const result = await curriculumService.copyClassDepartments(termId, sourceId);
      await load();
      setFeedback(`${result.copied} copied; ${result.skipped} existing or inapplicable assignments skipped. Copy applies to all eligible classes in this target term.`);
    } catch (err) { setError(getErrorMessage(err, "Could not copy specializations.")); }
    finally { lock.current = false; setPending(false); }
  };
  return <WorkspacePanel title="Class specializations by term" description="Select an exact session and term. Readiness and specialization requirements come from the academic service.">
    <fieldset disabled={pending} className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <SelectControl label="Academic session" value={sessionId} options={sessions.map((row) => ({ value: row.id, label: row.name }))} onChange={(id) => { setSessionId(id); setTermId(terms.find((row) => row.academic_session_id === id)?.id || ""); setSourceId(""); }} />
        <SelectControl label="Academic term" value={termId} options={terms.filter((row) => row.academic_session_id === sessionId).map((row) => ({ value: row.id, label: `${row.name.replaceAll("_", " ")} · ${row.status}` }))} onChange={(id) => { setTermId(id); setSourceId(""); }} />
        <SelectControl label="Academic level" value={levelId} options={levels.map((row) => ({ value: row.id, label: row.name }))} onChange={setLevelId} placeholder="All specialization levels" clearable />
      </div>
      {error ? <div role="alert" className="whitespace-pre-line text-sm text-error">{error}<Button type="button" variant="outline" onClick={load}>Refresh state</Button></div> : null}
      {contextError ? <div role="alert" className="text-sm text-error">{contextError}<Button type="button" variant="outline" onClick={() => setContextAttempt((value) => value + 1)}>Retry sessions and terms</Button></div> : null}
      {feedback ? <p role="status" className="text-sm text-success">{feedback}</p> : null}
      {selected.length && levelId && editable ? <div className="flex items-end gap-3">
        <SelectControl label={`Department for ${selected.length} selected classes`} value={departmentId} onChange={setDepartmentId} options={optionsFor(levelId)} />
        <Button type="button" disabled={!departmentId} onClick={() => assign(selected, departmentId)}>Assign selected</Button>
      </div> : null}
      {loading ? <p role="status">Loading term specializations…</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm">
        <thead><tr><th className="p-3">Select</th><th className="p-3">Class</th><th className="p-3">Specialization</th><th className="p-3">Readiness</th><th className="p-3">Assign department</th></tr></thead>
        <tbody>{visible.map((row) => <tr key={row.class_id} className="border-t border-border">
          <td className="p-3"><input type="checkbox" aria-label={`Select ${row.display_name}`} disabled={!editable || !levelId || !row.specialization_required} checked={selected.includes(row.class_id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, row.class_id] : current.filter((id) => id !== row.class_id))} /></td>
          <td className="p-3 font-semibold">{row.display_name}</td><td className="p-3">{row.department_name || (row.specialization_required ? "Not configured" : "Not required yet")}</td>
          <td className="p-3">{row.readiness.replaceAll("_", " ")}</td>
          <td className="p-3">{editable && row.specialization_required ? <SelectControl label={`Department for ${row.display_name}`} value={row.academic_level_department_id || ""} options={optionsFor(row.academic_level_id)} onChange={(id) => assign([row.class_id], id)} /> : "No action required"}</td>
        </tr>)}</tbody>
      </table>{!visible.length ? <p className="p-3">No classes in this selection.</p> : null}</div>}
      {!levelId ? <p className="text-sm text-text-muted">Choose a level to select classes for a bulk assignment.</p> : null}
      {String(term?.status).toLowerCase() === "draft" && sourceTerms.length ? <div className="flex items-end gap-3 border-t border-border pt-4">
        <SelectControl label="Copy from previous term" value={sourceId} onChange={setSourceId} options={sourceTerms.map((row) => ({ value: row.id, label: row.name.replaceAll("_", " ") }))} />
        <Button type="button" variant="outline" disabled={!sourceId} onClick={copy}>Copy previous term specializations</Button>
      </div> : null}
    </fieldset>
    {pending ? <p role="status" className="mt-3 text-sm">Saving specializations…</p> : null}
  </WorkspacePanel>;
}
