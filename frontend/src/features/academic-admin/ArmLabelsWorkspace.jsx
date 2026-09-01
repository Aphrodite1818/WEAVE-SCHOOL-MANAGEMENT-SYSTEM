import { Tags } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { armLabelService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import {
  FormActions,
  Input,
  RecordList,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";
import TypedConfirmationDialog from "./TypedConfirmationDialog";

const asItems = (value) => (Array.isArray(value) ? value : value?.items || []);
const lifecycleStatus = (item) =>
  item.archived_at ? "archived" : item.is_active ? "active" : "inactive";

function ArmLabelsWorkspace({ activeTab = "overview" }) {
  const { showError, showSuccess } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [armLabels, setArmLabels] = useState([]);
  const [label, setLabel] = useState("");
  const [editing, setEditing] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setArmLabels(asItems(await armLabelService.getArmLabels({ includeArchived: true })));
    } catch (error) {
      showError(getErrorMessage(error, "Could not load arm labels."));
    }
  }, [showError]);

  useEffect(() => {
    load();
  }, [load]);

  const visibleLabels = useMemo(
    () =>
      ["active", "inactive", "archived"].includes(activeTab)
        ? armLabels.filter((row) => lifecycleStatus(row) === activeTab)
        : armLabels,
    [activeTab, armLabels],
  );

  const selectView = (view) => {
    const next = new URLSearchParams(searchParams);
    next.set("view", view);
    next.delete("tab");
    setSearchParams(next, { replace: true });
  };

  const closeEditor = () => {
    setEditing(null);
    setLabel("");
    selectView("overview");
  };

  const save = async (event) => {
    event.preventDefault();
    if (!label.trim()) return;
    setSaving(true);
    try {
      if (editing) await armLabelService.updateArmLabel(editing.id, { label: label.trim() });
      else await armLabelService.createArmLabel({ label: label.trim() });
      showSuccess(editing ? "Arm label updated." : "Arm label created.");
      closeEditor();
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not save arm label."));
    } finally {
      setSaving(false);
    }
  };

  const runLifecycle = async () => {
    if (!pendingAction) return;
    const { item, action } = pendingAction;
    setSaving(item.id);
    try {
      if (action === "activate") await armLabelService.activateArmLabel(item.id);
      if (action === "deactivate") await armLabelService.deactivateArmLabel(item.id);
      if (action === "archive") await armLabelService.archiveArmLabel(item.id);
      if (action === "restore") await armLabelService.restoreArmLabel(item.id);
      showSuccess(`Arm label ${action}d.`);
      setPendingAction(null);
      await load();
    } catch (error) {
      showError(getErrorMessage(error, `Could not ${action} this arm label.`));
    } finally {
      setSaving(false);
    }
  };

  const actionConfig = pendingAction
    ? {
        activate: ["Activate arm label", "ACTIVATE_ARM_LABEL", "Activate"],
        deactivate: ["Deactivate arm label", "DEACTIVATE_ARM_LABEL", "Deactivate"],
        archive: ["Archive arm label", "ARCHIVE_ARM_LABEL", "Archive"],
        restore: ["Restore arm label", "RESTORE_ARM_LABEL", "Restore"],
      }[pendingAction.action]
    : null;
  const showEditor = activeTab === "create" || Boolean(editing);

  return (
    <>
      <WorkspaceGrid
        editor={
          showEditor ? (
            <WorkspacePanel
              title={editing ? "Edit arm label" : "Add arm label"}
              description="Create one reusable label that can be used across many levels."
            >
              <form className="space-y-3" onSubmit={save}>
                <Input
                  label="Arm label"
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                  placeholder="A"
                  required
                />
                <FormActions
                  submitting={Boolean(saving)}
                  submitLabel={editing ? "Save label" : "Add arm label"}
                  editing
                  onCancel={closeEditor}
                />
              </form>
            </WorkspacePanel>
          ) : null
        }
        content={
          activeTab === "create" && !editing ? null : (
            <RecordList
              title="Arm labels"
              description="Reusable class labels with explicit active, inactive, and archived states."
              actions={
                !showEditor ? (
                  <Button type="button" onClick={() => selectView("create")}>
                    Add arm label
                  </Button>
                ) : null
              }
              items={visibleLabels}
              emptyIcon={Tags}
              emptyTitle="No arm labels"
              emptyDescription="Add a label such as A, B, Science, or Arts."
              renderTitle={(item) => item.label}
              renderMeta={() => "Reusable across academic levels"}
              renderDescription={() =>
                "A label identifies a class arm; it does not own curriculum or progression rules."
              }
              renderStatus={lifecycleStatus}
              showInspector={!showEditor}
              onEdit={(item) => {
                setEditing(item);
                setLabel(item.label);
              }}
              canEdit={(item) => !item.archived_at}
              renderActions={(item) => {
                const status = lifecycleStatus(item);
                return (
                  <>
                    {status === "active" ? (
                      <Button
                        size="small"
                        variant="outline"
                        onClick={() => setPendingAction({ item, action: "deactivate" })}
                      >
                        Deactivate
                      </Button>
                    ) : null}
                    {status === "inactive" ? (
                      <Button
                        size="small"
                        variant="outline"
                        onClick={() => setPendingAction({ item, action: "activate" })}
                      >
                        Activate
                      </Button>
                    ) : null}
                    {status === "inactive" ? (
                      <Button
                        size="small"
                        variant="outline"
                        onClick={() => setPendingAction({ item, action: "archive" })}
                      >
                        Archive
                      </Button>
                    ) : null}
                    {status === "archived" ? (
                      <Button
                        size="small"
                        variant="outline"
                        onClick={() => setPendingAction({ item, action: "restore" })}
                      >
                        Restore
                      </Button>
                    ) : null}
                  </>
                );
              }}
            />
          )
        }
      />
      <TypedConfirmationDialog
        open={Boolean(pendingAction)}
        title={actionConfig?.[0]}
        description={`${pendingAction?.item?.label || "This label"} will move through the supported arm-label lifecycle. Classes using it are protected by backend dependency checks.`}
        confirmationText={actionConfig?.[1] || ""}
        confirmLabel={actionConfig?.[2]}
        variant={["deactivate", "archive"].includes(pendingAction?.action) ? "danger" : "primary"}
        isLoading={saving === pendingAction?.item?.id}
        onConfirm={runLifecycle}
        onCancel={() => setPendingAction(null)}
      />
    </>
  );
}

export default ArmLabelsWorkspace;
