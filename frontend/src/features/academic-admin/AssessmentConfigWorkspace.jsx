import { Settings2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { Input, WorkspacePanel } from "./AcademicWorkspacePrimitives";
import TypedConfirmationDialog from "./TypedConfirmationDialog";

const DEFAULT_CONFIG = { test_max: 20, assessment_max: 20, exam_max: 60 };

function AssessmentConfigWorkspace() {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [draft, setDraft] = useState(DEFAULT_CONFIG);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { showSuccess, showError, showWarning } = useToast();

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const response = (await academicService.getAssessmentConfig()) || DEFAULT_CONFIG;
      setConfig(response);
      setDraft(response);
    } catch (error) {
      showError(getErrorMessage(error, "Could not load assessment score limits."));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const total = useMemo(
    () => Number(draft.test_max || 0) + Number(draft.assessment_max || 0) + Number(draft.exam_max || 0),
    [draft],
  );

  const validateDraft = () => {
    const values = [draft.test_max, draft.assessment_max, draft.exam_max].map(Number);
    if (values.some((value) => !Number.isFinite(value) || value <= 0)) {
      showWarning("Every assessment component maximum must be greater than zero.");
      return null;
    }
    if (total !== 100) {
      showWarning("Assessment component maximums must total 100.");
      return null;
    }
    return values;
  };

  const requestSave = () => {
    if (!validateDraft()) return;
    setConfirming(true);
  };

  const save = async () => {
    const values = validateDraft();
    if (!values) return;

    setSaving(true);
    try {
      const updated = await academicService.updateAssessmentConfig({
        test_max: values[0],
        assessment_max: values[1],
        exam_max: values[2],
      });
      setConfig(updated);
      setDraft(updated);
      setEditing(false);
      setConfirming(false);
      showSuccess("Assessment score limits updated.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not update assessment score limits."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <WorkspacePanel
        title="Assessment score limits"
        description="Configure how the 100 available marks are divided before teachers enter results. These limits apply across result entry for this school."
      >
        {loading ? (
          <p className="text-sm text-text-muted">Loading assessment configuration...</p>
        ) : (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                ["test_max", "Test maximum"],
                ["assessment_max", "Assessment maximum"],
                ["exam_max", "Exam maximum"],
              ].map(([field, label]) => (
                <Input
                  key={field}
                  label={label}
                  type="number"
                  min="1"
                  max="100"
                  disabled={!editing}
                  value={draft[field]}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, [field]: event.target.value }))
                  }
                />
              ))}
            </div>

            <div className={`rounded-xl border px-4 py-3 text-sm ${total === 100 ? "border-success/30 bg-success/5 text-success" : "border-error/30 bg-error/5 text-error"}`}>
              Configured total: <span className="font-semibold">{total} / 100</span>
            </div>

            <div className="flex flex-wrap gap-2">
              {editing ? (
                <>
                  <Button type="button" disabled={saving || total !== 100} onClick={requestSave}>
                    Save limits
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={saving}
                    onClick={() => {
                      setDraft(config);
                      setEditing(false);
                    }}
                  >
                    Cancel
                  </Button>
                </>
              ) : (
                <Button type="button" variant="outline" onClick={() => setEditing(true)}>
                  <Settings2 className="mr-2 h-4 w-4" />
                  Configure limits
                </Button>
              )}
            </div>
          </div>
        )}
      </WorkspacePanel>

      <WorkspacePanel
        title="How these limits are used"
        description="Result entry validates each component against these values while the final score remains out of 100."
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl bg-surface-muted/40 px-4 py-3"><p className="text-xs uppercase tracking-wide text-text-muted">Test</p><p className="mt-1 text-xl font-semibold text-text">{config.test_max}</p></div>
          <div className="rounded-xl bg-surface-muted/40 px-4 py-3"><p className="text-xs uppercase tracking-wide text-text-muted">Assessment</p><p className="mt-1 text-xl font-semibold text-text">{config.assessment_max}</p></div>
          <div className="rounded-xl bg-surface-muted/40 px-4 py-3"><p className="text-xs uppercase tracking-wide text-text-muted">Exam</p><p className="mt-1 text-xl font-semibold text-text">{config.exam_max}</p></div>
        </div>
      </WorkspacePanel>

      <TypedConfirmationDialog
        open={confirming}
        title="Update assessment score limits"
        description={`Change the school-wide score allocation from ${config.test_max}/${config.assessment_max}/${config.exam_max} to ${draft.test_max}/${draft.assessment_max}/${draft.exam_max}? New score entry will immediately use these maximums.`}
        confirmationText="UPDATE_ASSESSMENT_LIMITS"
        confirmLabel="Update limits"
        variant="danger"
        isLoading={saving}
        onConfirm={save}
        onCancel={() => setConfirming(false)}
      />
    </div>
  );
}

export default AssessmentConfigWorkspace;
