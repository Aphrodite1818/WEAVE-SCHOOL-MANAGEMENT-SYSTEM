import { useEffect, useState } from "react";

import Modal from "../../components/ui/Modal";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";

function TypedConfirmationDialog({
  open,
  title,
  description,
  confirmationText,
  confirmLabel = "Confirm",
  variant = "danger",
  isLoading = false,
  confirmDisabled = false,
  onConfirm,
  onCancel,
  children,
}) {
  const [value, setValue] = useState("");

  useEffect(() => {
    if (!open) setValue("");
  }, [open]);

  const matches = value === confirmationText;

  return (
    <Modal
      open={open}
      title={title}
      description={description}
      onClose={isLoading ? undefined : onCancel}
      closeOnOverlay={!isLoading}
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant={variant}
            disabled={isLoading || !matches || confirmDisabled}
            onClick={() => onConfirm(value)}
          >
            {isLoading ? "Working..." : confirmLabel}
          </Button>
        </div>
      }
    >
      <div className="space-y-3">
        <p className="text-sm text-text-muted">
          Type{" "}
          <span className="font-semibold text-text">{confirmationText}</span> to
          continue.
        </p>
        <Input
          label="Confirmation"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          autoComplete="off"
          autoFocus
        />
        {children}
      </div>
    </Modal>
  );
}

export default TypedConfirmationDialog;
