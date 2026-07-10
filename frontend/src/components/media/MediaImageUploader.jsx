import { useMemo, useRef, useState } from "react";
import { Camera, ImagePlus, Loader2, Trash2, UploadCloud } from "lucide-react";

import { parseApiError } from "../../services/api";
import { cn } from "../../utils/cn";
import Button from "../ui/Button";

const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

const formatSize = (bytes) => {
  if (!bytes) return "0 MB";
  return `${(bytes / (1024 * 1024)).toFixed(bytes >= 1024 * 1024 ? 1 : 2)} MB`;
};

const getInitials = (value) => {
  const parts = String(value || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  const first = parts[0]?.charAt(0) || "";
  const second = parts.length > 1 ? parts[parts.length - 1]?.charAt(0) : "";
  return `${first}${second}`.toUpperCase() || "L";
};

function PreviewFrame({ variant, imageUrl, previewUrl, fallbackLabel }) {
  const src = previewUrl || imageUrl;
  const isLogo = variant === "logo";

  return (
    <div
      className={cn(
        "relative isolate flex shrink-0 items-center justify-center overflow-hidden border border-border bg-surface shadow-inner",
        isLogo
          ? "h-32 w-full rounded-[1.75rem] sm:h-36 md:w-56"
          : "mx-auto h-28 w-28 rounded-full sm:mx-0 sm:h-32 sm:w-32"
      )}
    >
      {src ? (
        <img
          src={src}
          alt=""
          className={cn("h-full w-full", isLogo ? "object-contain p-5" : "object-cover")}
        />
      ) : (
        <div
          className={cn(
            "flex h-full w-full flex-col items-center justify-center gap-2 bg-gradient-to-br from-primary-soft via-surface-muted to-accent-soft text-center text-primary",
            isLogo ? "px-4" : ""
          )}
        >
          {isLogo ? <ImagePlus className="h-8 w-8" /> : <Camera className="h-7 w-7" />}
          <span className={cn("font-black", isLogo ? "text-2xl" : "text-3xl")}>{getInitials(fallbackLabel)}</span>
        </div>
      )}

      <div className="pointer-events-none absolute inset-x-3 bottom-3 rounded-full border border-white/30 bg-black/35 px-3 py-1 text-center text-[11px] font-semibold text-white shadow-lg backdrop-blur-md">
        {src ? "Preview ready" : isLogo ? "School logo" : "Passport photo"}
      </div>
    </div>
  );
}

export default function MediaImageUploader({
  title,
  description,
  currentImageUrl,
  fallbackLabel,
  variant = "avatar",
  maxSizeBytes = 2 * 1024 * 1024,
  maxSizeLabel,
  onUpload,
  onDelete,
  onUploaded,
  onDeleted,
  disabled = false,
  className = "",
}) {
  const inputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState(null);

  const resolvedMaxSizeLabel = maxSizeLabel || formatSize(maxSizeBytes);

  const helperText = useMemo(
    () => `JPG, PNG, or WebP. Maximum ${resolvedMaxSizeLabel}.`,
    [resolvedMaxSizeLabel]
  );

  const resetSelection = () => {
    setSelectedFile(null);
    setError(null);

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }

    if (inputRef.current) inputRef.current.value = "";
  };

  const validateFile = (file) => {
    if (!file) return "Choose an image to upload.";

    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      return "Please upload a JPG, PNG, or WebP image.";
    }

    if (file.size > maxSizeBytes) {
      return `This file is too large. Maximum size is ${resolvedMaxSizeLabel}.`;
    }

    return null;
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    const validationMessage = validateFile(file);

    if (validationMessage) {
      resetSelection();
      setError(validationMessage);
      return;
    }

    if (previewUrl) URL.revokeObjectURL(previewUrl);

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setError(null);
  };

  const handleUpload = async () => {
    if (!selectedFile || !onUpload) return;

    setIsUploading(true);
    setError(null);

    try {
      const response = await onUpload(selectedFile);
      onUploaded?.(response);
      resetSelection();
    } catch (err) {
      const parsed = parseApiError(err, "Failed to upload image.");
      setError(parsed.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async () => {
    if (!onDelete) return;
    if (!currentImageUrl && !previewUrl) return;
    if (!window.confirm("Remove this image?")) return;

    setIsDeleting(true);
    setError(null);

    try {
      const response = await onDelete();
      onDeleted?.(response);
      resetSelection();
    } catch (err) {
      const parsed = parseApiError(err, "Failed to remove image.");
      setError(parsed.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const isBusy = disabled || isUploading || isDeleting;

  return (
    <section
      className={cn(
        "rounded-[2rem] border border-border bg-surface/95 p-4 shadow-premium sm:p-5",
        className
      )}
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <PreviewFrame
          variant={variant}
          imageUrl={currentImageUrl}
          previewUrl={previewUrl}
          fallbackLabel={fallbackLabel || title}
        />

        <div className="min-w-0 flex-1 space-y-4 md:pl-2">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">
              Media asset
            </p>
            <h3 className="mt-1 text-lg font-bold text-text sm:text-xl">{title}</h3>
            {description ? (
              <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p>
            ) : null}
          </div>

          <div className="rounded-2xl border border-border bg-surface-muted/40 p-3 text-xs leading-5 text-text-muted">
            {helperText}
          </div>

          <input
            ref={inputRef}
            type="file"
            accept={ALLOWED_IMAGE_TYPES.join(",")}
            className="hidden"
            onChange={handleFileChange}
            disabled={isBusy}
          />

          {selectedFile ? (
            <div className="rounded-2xl border border-primary/20 bg-primary-soft/50 px-3 py-2 text-xs font-semibold text-primary">
              Selected: {selectedFile.name} · {formatSize(selectedFile.size)}
            </div>
          ) : null}

          {error ? (
            <div className="rounded-2xl border border-error/25 bg-error-soft px-3 py-2 text-sm font-medium text-error">
              {error}
            </div>
          ) : null}

          <div className="grid gap-2 sm:flex sm:flex-wrap">
            <Button
              type="button"
              variant="outline"
              className="w-full sm:w-auto"
              disabled={isBusy}
              onClick={() => inputRef.current?.click()}
            >
              <UploadCloud className="h-4 w-4" />
              Choose image
            </Button>

            <Button
              type="button"
              className="w-full sm:w-auto"
              disabled={isBusy || !selectedFile}
              onClick={handleUpload}
            >
              {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />}
              {isUploading ? "Uploading..." : "Upload"}
            </Button>

            {(currentImageUrl || previewUrl) && onDelete ? (
              <Button
                type="button"
                variant="danger"
                className="w-full sm:w-auto"
                disabled={isBusy}
                onClick={previewUrl && !currentImageUrl ? resetSelection : handleDelete}
              >
                {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                {previewUrl && !currentImageUrl ? "Clear preview" : isDeleting ? "Removing..." : "Remove"}
              </Button>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
