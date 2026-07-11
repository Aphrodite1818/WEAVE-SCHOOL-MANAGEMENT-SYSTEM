import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  ImageIcon,
  LoaderCircle,
  RotateCcw,
  Trash2,
  UploadCloud,
} from "lucide-react";

import Button from "../ui/Button";
import Avatar from "../ui/Avatar";
import { authSession, parseApiError } from "../../services/api";
import { mediaService } from "../../services/mediaService";
import { getAvatarSrcFromRecord, getUserDisplayName } from "../../utils/user";
import { useToast } from "../../hooks/useToast";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];

const readPreview = (file) => URL.createObjectURL(file);

const cropProfilePhoto = (file, zoom) => new Promise((resolve, reject) => {
  const image = new Image();
  const sourceUrl = URL.createObjectURL(file);
  image.onload = () => {
    const cropSize = Math.min(image.naturalWidth, image.naturalHeight) / (zoom / 100);
    const sourceX = (image.naturalWidth - cropSize) / 2;
    const sourceY = (image.naturalHeight - cropSize) / 2;
    const canvas = document.createElement("canvas");
    canvas.width = 900;
    canvas.height = 900;
    const context = canvas.getContext("2d");
    context.drawImage(image, sourceX, sourceY, cropSize, cropSize, 0, 0, 900, 900);
    canvas.toBlob((blob) => {
      URL.revokeObjectURL(sourceUrl);
      if (!blob) {
        reject(new Error("The selected image could not be cropped."));
        return;
      }
      resolve(new File([blob], "profile-photo.jpg", { type: "image/jpeg" }));
    }, "image/jpeg", 0.9);
  };
  image.onerror = () => {
    URL.revokeObjectURL(sourceUrl);
    reject(new Error("The selected image could not be read."));
  };
  image.src = sourceUrl;
});

function validateImage(file, maxBytes) {
  if (!ACCEPTED_TYPES.includes(file.type)) {
    return "Choose a PNG, JPG, or WebP image.";
  }
  if (file.size > maxBytes) {
    return `The image must be smaller than ${Math.round(maxBytes / 1024 / 1024)} MB.`;
  }
  return null;
}

function UploadDropzone({ label, inputRef, onFile, disabled, compact = false }) {
  const [dragging, setDragging] = useState(false);

  return (
    <div
      className={`flex flex-col items-center justify-center rounded-2xl border border-dashed px-5 text-center transition ${
        compact ? "min-h-40" : "min-h-60"
      } ${dragging ? "border-primary bg-primary-subtle" : "border-primary/55 bg-surface"}`}
      onDragEnter={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        const file = event.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-soft text-primary">
        <UploadCloud className="h-6 w-6" aria-hidden="true" />
      </span>
      <p className="mt-4 text-sm font-semibold text-text">Drop an image here</p>
      <p className="mt-1 text-xs text-text-muted">or</p>
      <Button
        type="button"
        variant="outline"
        className="mt-3 min-h-11 bg-surface"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        Browse files
      </Button>
      <span className="sr-only">{label}</span>
    </div>
  );
}

function AssetStatus({ label, imageUrl, onRemove, busy }) {
  if (!imageUrl) return null;

  return (
    <div className="mt-4 flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <CheckCircle2 className="h-5 w-5 shrink-0 text-success" aria-hidden="true" />
        <div>
          <p className="text-sm font-semibold text-text">{label} uploaded</p>
          <p className="text-xs text-text-muted">Ready to use across your workspace</p>
        </div>
      </div>
      <Button type="button" variant="ghost" className="justify-start text-error hover:bg-error-soft hover:text-error sm:justify-center" onClick={onRemove} disabled={busy}>
        <Trash2 className="h-4 w-4" aria-hidden="true" />
        Remove
      </Button>
    </div>
  );
}

function ProfileMediaManager({ role, user: initialUser }) {
  const normalizedRole = String(role || "").toLowerCase();
  const supportsPassport = ["admin", "teacher", "student"].includes(normalizedRole);
  const supportsLogo = normalizedRole === "admin";
  const [user, setUser] = useState(initialUser);
  const [photoFile, setPhotoFile] = useState(null);
  const [photoPreview, setPhotoPreview] = useState(null);
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(null);
  const [zoom, setZoom] = useState(100);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const photoInputRef = useRef(null);
  const logoInputRef = useRef(null);
  const { showSuccess, showError } = useToast();

  const savedPhoto = getAvatarSrcFromRecord(user);
  const savedLogo = user?.tenant_logo_url || user?.tenant?.logo_url || null;
  const displayName = getUserDisplayName(user);

  useEffect(() => () => {
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    if (logoPreview) URL.revokeObjectURL(logoPreview);
  }, [photoPreview, logoPreview]);

  const choosePhoto = (file) => {
    const nextError = validateImage(file, 2 * 1024 * 1024);
    if (nextError) {
      setError(nextError);
      return;
    }
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    setPhotoFile(file);
    setPhotoPreview(readPreview(file));
    setZoom(100);
    setError(null);
  };

  const chooseLogo = (file) => {
    const nextError = validateImage(file, 1024 * 1024);
    if (nextError) {
      setError(nextError);
      return;
    }
    if (logoPreview) URL.revokeObjectURL(logoPreview);
    setLogoFile(file);
    setLogoPreview(readPreview(file));
    setError(null);
  };

  const persistUser = (patch) => {
    const nextUser = { ...user, ...patch };
    if (patch.tenant_logo_url !== undefined) {
      nextUser.tenant = { ...(user?.tenant || {}), logo_url: patch.tenant_logo_url };
    }
    setUser(nextUser);
    authSession.setUser(nextUser, { remember: authSession.getRememberPreference() });
  };

  const handleUpload = async (kind) => {
    const selectedFile = kind === "photo" ? photoFile : logoFile;
    if (!selectedFile) return;
    setBusy(kind);
    setError(null);
    try {
      const file = kind === "photo"
        ? await cropProfilePhoto(selectedFile, zoom)
        : selectedFile;
      const response = kind === "photo"
        ? await mediaService.uploadProfilePhoto(file)
        : await mediaService.uploadSchoolLogo(file);
      const renderUrl = response?.render_url || response?.media_asset?.cdn_url || response?.media_asset?.public_url;
      if (kind === "photo") {
        persistUser({ passport_photo_url: renderUrl });
        setPhotoFile(null);
        setPhotoPreview(null);
      } else {
        persistUser({ tenant_logo_url: renderUrl });
        setLogoFile(null);
        setLogoPreview(null);
      }
      showSuccess(kind === "photo" ? "Profile photo uploaded." : "School logo uploaded.");
    } catch (uploadError) {
      const parsed = parseApiError(uploadError, "The image could not be uploaded.");
      setError(parsed.message);
      showError(parsed.message);
    } finally {
      setBusy(null);
    }
  };

  const handleRemove = async (kind) => {
    setBusy(`remove-${kind}`);
    setError(null);
    try {
      if (kind === "photo") {
        await mediaService.deleteProfilePhoto();
        persistUser({ passport_photo_url: null });
      } else {
        await mediaService.deleteSchoolLogo();
        persistUser({ tenant_logo_url: null });
      }
      showSuccess(kind === "photo" ? "Profile photo removed." : "School logo removed.");
    } catch (removeError) {
      const parsed = parseApiError(removeError, "The image could not be removed.");
      setError(parsed.message);
      showError(parsed.message);
    } finally {
      setBusy(null);
    }
  };

  if (!supportsPassport && !supportsLogo) return null;

  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-surface shadow-sm" aria-labelledby="media-heading">
      <div className="border-b border-border px-4 py-5 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-primary">Profile setup</p>
            <h2 id="media-heading" className="mt-1 text-xl font-semibold sm:text-2xl">Photos &amp; logo</h2>
            <p className="mt-1 max-w-2xl text-sm text-text-muted">Add clear, recognizable images that represent you and your school across the workspace.</p>
          </div>
          <div className="flex items-center gap-2 text-xs font-semibold text-success">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            Secure image upload
          </div>
        </div>
      </div>

      {error ? <div role="alert" className="mx-4 mt-4 rounded-xl border border-error/25 bg-error-soft px-4 py-3 text-sm font-medium text-error sm:mx-6 lg:mx-8">{error}</div> : null}

      <div className={`grid ${supportsLogo ? "lg:grid-cols-[minmax(0,1.45fr)_minmax(19rem,0.8fr)]" : ""}`}>
        {supportsPassport ? (
          <div className="p-4 sm:p-6 lg:p-8">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold">Personal photo</h3>
                <p className="mt-1 text-sm text-text-muted">Use a clear passport-style image with your face centered.</p>
              </div>
              {savedPhoto ? <span className="rounded-full bg-success-soft px-3 py-1 text-xs font-semibold text-success-hover">Uploaded</span> : null}
            </div>

            <div className="mt-5 grid gap-5 md:grid-cols-[14rem_minmax(0,1fr)]">
              <div>
                <input ref={photoInputRef} className="sr-only" type="file" accept={ACCEPTED_TYPES.join(",")} onChange={(event) => event.target.files?.[0] && choosePhoto(event.target.files[0])} />
                <UploadDropzone label="Personal photo" inputRef={photoInputRef} onFile={choosePhoto} disabled={Boolean(busy)} />
                <p className="mt-2 text-center text-xs text-text-muted">PNG, JPG or WebP · Max 2 MB</p>
              </div>

              <div className="flex min-h-60 flex-col items-center justify-center rounded-2xl bg-surface-muted/60 p-5">
                <div className="relative h-44 w-44 overflow-hidden rounded-full border-4 border-surface bg-surface shadow-sm ring-1 ring-border">
                  {photoPreview ? <img src={photoPreview} alt="Selected profile preview" className="h-full w-full object-cover" style={{ transform: `scale(${zoom / 100})` }} /> : <Avatar user={user} name={displayName} className="h-full w-full text-4xl ring-0" />}
                </div>
                {photoPreview ? (
                  <div className="mt-5 w-full max-w-xs">
                    <div className="flex items-center justify-between text-xs font-semibold text-text-soft"><span>Adjust crop</span><span>{zoom}%</span></div>
                    <input aria-label="Photo zoom" className="mt-2 w-full accent-primary" type="range" min="100" max="160" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} />
                    <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                      <Button type="button" variant="outline" className="flex-1" onClick={() => { setPhotoFile(null); setPhotoPreview(null); setZoom(100); }} disabled={Boolean(busy)}><RotateCcw className="h-4 w-4" />Reset</Button>
                      <Button type="button" className="flex-1 bg-primary" onClick={() => handleUpload("photo")} disabled={Boolean(busy)}>{busy === "photo" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}Upload photo</Button>
                    </div>
                  </div>
                ) : <p className="mt-4 text-sm text-text-muted">{savedPhoto ? "Current profile photo" : "Your preview will appear here"}</p>}
              </div>
            </div>
            <AssetStatus label="Profile photo" imageUrl={savedPhoto} onRemove={() => handleRemove("photo")} busy={Boolean(busy)} />
          </div>
        ) : null}

        {supportsLogo ? (
          <aside className="border-t border-border bg-surface-muted/35 p-4 sm:p-6 lg:border-l lg:border-t-0 lg:p-8">
            <h3 className="text-base font-semibold">School logo</h3>
            <p className="mt-1 text-sm text-text-muted">Use a high-resolution logo with a plain or transparent background.</p>
            <div className="mt-5 flex min-h-44 items-center justify-center rounded-2xl border border-border bg-surface p-5">
              {logoPreview || savedLogo ? <img src={logoPreview || savedLogo} alt="School logo preview" className="max-h-32 max-w-full object-contain" /> : <div className="text-center text-text-faint"><ImageIcon className="mx-auto h-10 w-10" /><p className="mt-2 text-sm">No school logo yet</p></div>}
            </div>
            <div className="mt-4">
              <input ref={logoInputRef} className="sr-only" type="file" accept={ACCEPTED_TYPES.join(",")} onChange={(event) => event.target.files?.[0] && chooseLogo(event.target.files[0])} />
              <UploadDropzone compact label="School logo" inputRef={logoInputRef} onFile={chooseLogo} disabled={Boolean(busy)} />
              <p className="mt-2 text-center text-xs text-text-muted">PNG, JPG or WebP · Max 1 MB</p>
            </div>
            {logoFile ? <Button type="button" className="mt-4 w-full bg-primary" onClick={() => handleUpload("logo")} disabled={Boolean(busy)}>{busy === "logo" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}Upload school logo</Button> : null}
            <AssetStatus label="School logo" imageUrl={savedLogo} onRemove={() => handleRemove("logo")} busy={Boolean(busy)} />
          </aside>
        ) : null}
      </div>
    </section>
  );
}

export default ProfileMediaManager;
