import { CheckCircle2, LockKeyhole } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import Button from "../ui/Button";
import Card from "../ui/Card";

const selectedFromGroup = (group) =>
  (group?.subjects || [])
    .filter((subject) => subject.selected)
    .map((subject) => subject.curriculum_subject_id);

export default function StudentElectiveSelectionPanel({
  workspace,
  onSave,
}) {
  const groups = useMemo(() => workspace?.groups || [], [workspace]);
  const [selectedByGroup, setSelectedByGroup] = useState({});
  const [savingGroupId, setSavingGroupId] = useState("");
  const [errorByGroup, setErrorByGroup] = useState({});

  useEffect(() => {
    setSelectedByGroup(
      Object.fromEntries(
        groups.map((group) => [
          group.elective_group_id,
          selectedFromGroup(group),
        ]),
      ),
    );
    setErrorByGroup({});
  }, [groups]);

  const originalByGroup = useMemo(
    () =>
      Object.fromEntries(
        groups.map((group) => [
          group.elective_group_id,
          selectedFromGroup(group),
        ]),
      ),
    [groups],
  );

  if (!groups.length) return null;

  const toggleSubject = (group, subjectId) => {
    if (group.locked || savingGroupId) return;
    setSelectedByGroup((current) => {
      const selected = new Set(current[group.elective_group_id] || []);
      if (selected.has(subjectId)) {
        selected.delete(subjectId);
      } else {
        if (selected.size >= group.maximum_choices) return current;
        selected.add(subjectId);
      }
      return {
        ...current,
        [group.elective_group_id]: [...selected],
      };
    });
    setErrorByGroup((current) => ({
      ...current,
      [group.elective_group_id]: "",
    }));
  };

  const saveGroup = async (group) => {
    const selected = selectedByGroup[group.elective_group_id] || [];
    if (
      selected.length < group.minimum_choices ||
      selected.length > group.maximum_choices
    ) {
      setErrorByGroup((current) => ({
        ...current,
        [group.elective_group_id]: `Choose between ${group.minimum_choices} and ${group.maximum_choices} subject(s).`,
      }));
      return;
    }

    setSavingGroupId(group.elective_group_id);
    setErrorByGroup((current) => ({
      ...current,
      [group.elective_group_id]: "",
    }));
    try {
      await onSave(group.elective_group_id, selected);
    } catch (error) {
      setErrorByGroup((current) => ({
        ...current,
        [group.elective_group_id]:
          error?.message || "We could not save your elective choices.",
      }));
    } finally {
      setSavingGroupId("");
    }
  };

  return (
    <Card className="border-primary/15 bg-primary-soft/20 p-4 sm:p-5">
      <div className="mb-4">
        <p className="text-sm font-bold text-text">Choose your electives</p>
        <p className="mt-1 text-xs leading-5 text-text-muted">
          Your choices stay in place across terms. You can change a group until an
          assessment score has been recorded for that group in the current term.
        </p>
      </div>

      <div className="space-y-4">
        {groups.map((group) => {
          const selected = selectedByGroup[group.elective_group_id] || [];
          const original = originalByGroup[group.elective_group_id] || [];
          const changed =
            selected.length !== original.length ||
            selected.some((id) => !original.includes(id));
          const saving = savingGroupId === group.elective_group_id;
          const rangeLabel =
            group.minimum_choices === group.maximum_choices
              ? `Choose ${group.maximum_choices}`
              : `Choose ${group.minimum_choices}–${group.maximum_choices}`;

          return (
            <section
              key={group.elective_group_id}
              className="rounded-2xl border border-border bg-surface p-3.5 sm:p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-text">{group.name}</p>
                    {group.locked ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-surface-muted px-2 py-0.5 text-[11px] font-semibold text-text-muted">
                        <LockKeyhole className="h-3 w-3" /> Locked
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-text-muted">
                    {rangeLabel} · {selected.length} selected
                  </p>
                </div>
                {!group.locked ? (
                  <Button
                    size="sm"
                    onClick={() => saveGroup(group)}
                    disabled={!changed || saving || Boolean(savingGroupId && !saving)}
                  >
                    {saving ? "Saving…" : "Save choices"}
                  </Button>
                ) : null}
              </div>

              {group.locked && group.locked_reason ? (
                <p className="mt-3 rounded-xl bg-surface-muted px-3 py-2 text-xs leading-5 text-text-muted">
                  {group.locked_reason}
                </p>
              ) : null}

              <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {(group.subjects || []).map((subject) => {
                  const checked = selected.includes(subject.curriculum_subject_id);
                  return (
                    <button
                      key={subject.curriculum_subject_id}
                      type="button"
                      disabled={group.locked || Boolean(savingGroupId)}
                      onClick={() =>
                        toggleSubject(group, subject.curriculum_subject_id)
                      }
                      className={`flex min-h-14 items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition ${
                        checked
                          ? "border-primary/40 bg-primary-soft/60"
                          : "border-border bg-surface hover:border-primary/25 hover:bg-surface-muted"
                      } disabled:cursor-not-allowed disabled:opacity-70`}
                    >
                      <span
                        className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border ${
                          checked
                            ? "border-primary bg-primary text-white"
                            : "border-border bg-surface"
                        }`}
                        aria-hidden="true"
                      >
                        {checked ? <CheckCircle2 className="h-4 w-4" /> : null}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold text-text">
                          {subject.subject_name}
                        </span>
                        {subject.subject_code ? (
                          <span className="block text-[11px] text-text-muted">
                            {subject.subject_code}
                          </span>
                        ) : null}
                      </span>
                    </button>
                  );
                })}
              </div>

              {errorByGroup[group.elective_group_id] ? (
                <p className="mt-3 text-xs font-medium text-danger">
                  {errorByGroup[group.elective_group_id]}
                </p>
              ) : null}
            </section>
          );
        })}
      </div>
    </Card>
  );
}
