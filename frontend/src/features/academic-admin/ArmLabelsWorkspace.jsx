import { useCallback, useEffect, useState } from "react";

import Badge from "../../components/ui/Badge";
import { useToast } from "../../hooks/useToast";
import { armLabelService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import {
  FormActions,
  Input,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const asItems = (value) => (Array.isArray(value) ? value : value?.items || []);

function ArmLabelsWorkspace({ activeTab = "overview" }) {
  const { showError, showSuccess } = useToast();
  const [armLabels, setArmLabels] = useState([]);
  const [label, setLabel] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setArmLabels(
        asItems(await armLabelService.getArmLabels({ includeArchived: true })),
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not load arm labels."));
    }
  }, [showError]);

  useEffect(() => {
    load();
  }, [load]);

  const create = async (event) => {
    event.preventDefault();
    if (!label.trim()) return;
    setSaving(true);
    try {
      await armLabelService.createArmLabel({ label: label.trim() });
      setLabel("");
      showSuccess("Arm label created.");
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not create arm label."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <WorkspaceGrid
      editor={
        activeTab === "create" ? (
          <WorkspacePanel
            title="Add arm label"
            description="Create one reusable label that can be used across many levels."
          >
            <form className="space-y-3" onSubmit={create}>
              <Input
                label="Arm label"
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                placeholder="A"
                required
              />
              <FormActions submitting={saving} submitLabel="Add arm label" />
            </form>
          </WorkspacePanel>
        ) : null
      }
      content={
        <WorkspacePanel
          title="Arm labels"
          description="Reusable labels available when creating or editing classes."
        >
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {armLabels.map((item) => (
              <div
                key={item.id}
                className="rounded-2xl border border-border/70 bg-surface p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-lg font-semibold text-text">
                    {item.label}
                  </p>
                  <Badge
                    variant={
                      item.is_active && !item.archived_at
                        ? "success"
                        : "warning"
                    }
                  >
                    {item.archived_at
                      ? "Archived"
                      : item.is_active
                        ? "Active"
                        : "Inactive"}
                  </Badge>
                </div>
              </div>
            ))}
            {!armLabels.length ? (
              <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-text-muted">
                No arm labels yet.
              </div>
            ) : null}
          </div>
        </WorkspacePanel>
      }
    />
  );
}

export default ArmLabelsWorkspace;
