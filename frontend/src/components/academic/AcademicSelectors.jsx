import { Children, isValidElement } from "react";

import SearchableSelect from "../ui/SearchableSelect";

const fieldClass =
  "h-10 min-h-10 w-full rounded-xl border border-border bg-background/70 px-3 text-[13px] font-medium text-text outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10 disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-text-muted sm:h-[38px] sm:min-h-[38px]";

const nodeText = (node) => {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  if (isValidElement(node)) return nodeText(node.props.children);
  return "";
};

const optionsFromChildren = (children) => {
  const options = [];
  Children.forEach(children, (child) => {
    if (!isValidElement(child)) return;
    if (child.type === "option") {
      options.push({
        value: child.props.value ?? "",
        label: nodeText(child.props.children).trim(),
        disabled: Boolean(child.props.disabled),
      });
      return;
    }
    if (child.props?.children) options.push(...optionsFromChildren(child.props.children));
  });
  return options;
};

export function SelectField({
  label,
  value,
  onChange,
  children,
  options,
  disabled = false,
  required = false,
  className = "",
  placeholder = "Select an option",
  searchPlaceholder,
  searchable = true,
}) {
  const normalizedOptions = options || optionsFromChildren(children);
  const explicitPlaceholder = normalizedOptions.find((option) => String(option.value) === "");
  const selectableOptions = normalizedOptions.filter(
    (option) => String(option.value) !== "" && !option.disabled,
  );

  return (
    <SearchableSelect
      label={label}
      value={value}
      onChange={onChange}
      options={selectableOptions}
      disabled={disabled}
      required={required}
      className={className}
      placeholder={explicitPlaceholder?.label || placeholder}
      searchPlaceholder={searchPlaceholder || `Search ${String(label || "options").toLowerCase()}`}
      searchable={searchable}
      buttonClassName="h-10 min-h-10 bg-background/70 px-3 text-[13px] sm:h-[38px] sm:min-h-[38px]"
    />
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
