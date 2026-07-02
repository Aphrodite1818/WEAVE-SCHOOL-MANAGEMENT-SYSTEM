const fieldClass =
  "h-10 min-h-10 w-full rounded-xl border border-border bg-background/70 px-3 text-[13px] font-medium text-text outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10 disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-text-muted sm:h-[38px] sm:min-h-[38px]";

export function SelectField({
  label,
  value,
  onChange,
  children,
  disabled = false,
  required = false,
  className = "",
}) {
  return (
    <label className={`block min-w-0 ${className}`}>
      <span className="mb-1.5 block text-[11.5px] font-semibold uppercase tracking-wide text-text-muted">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        required={required}
        className={fieldClass}
      >
        {children}
      </select>
    </label>
  );
}

export function TextField({
  label,
  value,
  onChange,
  type = "text",
  min,
  max,
  placeholder,
  required = false,
  disabled = false,
  className = "",
}) {
  return (
    <label className={`block min-w-0 ${className}`}>
      <span className="mb-1.5 block text-[11.5px] font-semibold uppercase tracking-wide text-text-muted">
        {label}
      </span>
      <input
        type={type}
        min={min}
        max={max}
        value={value}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className={fieldClass}
      />
    </label>
  );
}

export function CheckboxField({ label, checked, onChange, helperText, disabled = false, className = "" }) {
  return (
    <label className={`block min-w-0 ${className}`}>
      <span className="flex h-10 min-h-10 items-center gap-3 rounded-xl border border-border bg-background/70 px-3 text-[13px] font-medium text-text-soft sm:h-[38px] sm:min-h-[38px]">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
          className="h-4 w-4 rounded border-border text-primary focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
        />
        {label}
      </span>
      {helperText ? <span className="mt-1 block text-[10.5px] text-text-faint">{helperText}</span> : null}
    </label>
  );
}
