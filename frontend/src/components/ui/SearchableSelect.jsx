import { Check, ChevronDown, Search, X } from "lucide-react";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { cn } from "../../utils/cn";

const optionText = (option) =>
  [
    option?.label,
    option?.description,
    Array.isArray(option?.keywords)
      ? option.keywords.join(" ")
      : option?.keywords,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

function useMobileViewport() {
  const [mobile, setMobile] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(max-width: 767px)").matches
      : false,
  );

  useEffect(() => {
    const query = window.matchMedia("(max-width: 767px)");
    const update = () => setMobile(query.matches);
    update();
    query.addEventListener?.("change", update);
    query.addListener?.(update);
    return () => {
      query.removeEventListener?.("change", update);
      query.removeListener?.(update);
    };
  }, []);

  return mobile;
}

function SearchableSelect({
  label,
  value = "",
  onChange,
  options = [],
  placeholder = "Select an option",
  searchPlaceholder = "Type to search",
  emptyMessage = "No matching options",
  disabled = false,
  required = false,
  searchable = true,
  clearable = false,
  error,
  helperText,
  className = "",
  buttonClassName = "",
  name,
}) {
  const id = useId();
  const containerRef = useRef(null);
  const searchRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const mobile = useMobileViewport();

  const normalizedValue = String(value ?? "");
  const selected = useMemo(
    () => options.find((option) => String(option.value) === normalizedValue) || null,
    [normalizedValue, options],
  );
  const filteredOptions = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return options;
    return options.filter((option) => optionText(option).includes(normalizedQuery));
  }, [options, query]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      return undefined;
    }

    const frame = window.requestAnimationFrame(() => searchRef.current?.focus());
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    const closeOnOutsideClick = (event) => {
      if (mobile) return;
      if (!containerRef.current?.contains(event.target)) setOpen(false);
    };

    document.addEventListener("keydown", closeOnEscape);
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("pointerdown", closeOnOutsideClick);
    };
  }, [mobile, open]);

  const selectOption = (option) => {
    if (option.disabled) return;
    onChange?.(String(option.value));
    setOpen(false);
    setQuery("");
  };

  const panel = (
    <div
      id={`${id}-listbox`}
      role="listbox"
      aria-label={label || placeholder}
      className={cn(
        "overflow-hidden border border-border bg-surface shadow-xl",
        mobile
          ? "fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-[120] max-h-[72dvh] rounded-[1.4rem]"
          : "absolute left-0 right-0 top-[calc(100%+0.45rem)] z-[80] max-h-80 rounded-2xl",
      )}
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-3 md:hidden">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text">{label || placeholder}</p>
          <p className="mt-0.5 text-xs text-text-muted">Search and choose one option</p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-text-muted transition hover:bg-surface-muted hover:text-text"
          aria-label="Close options"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {searchable ? (
        <div className="border-b border-border p-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-faint" />
            <input
              ref={searchRef}
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={searchPlaceholder}
              className="input-base pl-10"
              aria-label={searchPlaceholder}
            />
          </div>
        </div>
      ) : null}

      <div className="max-h-[52dvh] overflow-y-auto overscroll-contain p-2 md:max-h-64">
        {filteredOptions.length ? (
          filteredOptions.map((option) => {
            const isSelected = String(option.value) === normalizedValue;
            return (
              <button
                key={String(option.value)}
                type="button"
                role="option"
                aria-selected={isSelected}
                disabled={option.disabled}
                onClick={() => selectOption(option)}
                className={cn(
                  "flex min-h-11 w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition",
                  isSelected
                    ? "bg-primary-soft text-primary"
                    : "text-text-soft hover:bg-surface-muted hover:text-text",
                  option.disabled && "cursor-not-allowed opacity-45",
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold">
                    {option.label}
                  </span>
                  {option.description ? (
                    <span className="mt-0.5 block truncate text-xs text-text-muted">
                      {option.description}
                    </span>
                  ) : null}
                </span>
                {isSelected ? <Check className="h-4 w-4 shrink-0" /> : null}
              </button>
            );
          })
        ) : (
          <div className="px-3 py-8 text-center">
            <Search className="mx-auto h-5 w-5 text-text-faint" />
            <p className="mt-2 text-sm font-medium text-text-muted">{emptyMessage}</p>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className={cn("block min-w-0", className)} ref={containerRef}>
      {label ? (
        <span className="mb-1.5 block text-sm font-semibold text-text-soft">
          {label}
        </span>
      ) : null}
      <div className="relative">
        <button
          type="button"
          className={cn(
            "input-base flex min-h-11 items-center justify-between gap-3 text-left",
            clearable && selected && "pr-16",
            !selected && "text-text-muted",
            disabled && "cursor-not-allowed opacity-60",
            buttonClassName,
          )}
          disabled={disabled}
          role="combobox"
          aria-expanded={open}
          aria-controls={`${id}-listbox`}
          aria-haspopup="listbox"
          aria-required={required}
          onClick={() => setOpen((current) => !current)}
        >
          <span className="min-w-0 flex-1 truncate">
            {selected?.label || placeholder}
          </span>
          <ChevronDown
            className={cn("h-4 w-4 shrink-0 text-text-faint transition", open && "rotate-180")}
          />
        </button>
        {clearable && selected && !disabled ? (
          <button
            type="button"
            aria-label="Clear selection"
            onClick={() => onChange?.("")}
            className="absolute right-8 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-lg text-text-faint transition hover:bg-surface-muted hover:text-text"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : null}
        {!mobile && open ? panel : null}
      </div>

      {name ? <input type="hidden" name={name} value={normalizedValue} /> : null}
      {helperText && !error ? (
        <span className="mt-1 block text-xs text-text-muted">{helperText}</span>
      ) : null}
      {error ? <span className="mt-1 block text-xs text-error">{error}</span> : null}

      {mobile && open && typeof document !== "undefined"
        ? createPortal(
            <>
              <button
                type="button"
                aria-label="Close options"
                className="fixed inset-0 z-[110] bg-slate-950/45 backdrop-blur-[1px]"
                onClick={() => setOpen(false)}
              />
              {panel}
            </>,
            document.body,
          )
        : null}
    </div>
  );
}

export default SearchableSelect;
