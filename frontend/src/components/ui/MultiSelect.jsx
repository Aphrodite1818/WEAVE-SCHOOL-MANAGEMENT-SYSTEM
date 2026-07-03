import { useMemo, useState } from "react";
import { Check, Search, X } from "lucide-react";

function MultiSelect({
  label,
  name,
  value = [],
  options = [],
  placeholder = "Search and select",
  searchPlaceholder = "Search options",
  error,
  disabled = false,
  required = false,
  onChange,
}) {
  const [query, setQuery] = useState("");

  const normalizedValue = useMemo(() => (Array.isArray(value) ? value : []), [value]);
  const selectedOptions = useMemo(
    () => options.filter((option) => normalizedValue.includes(option.value)),
    [normalizedValue, options]
  );
  const filteredOptions = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return options;
    return options.filter((option) =>
      String(option.label || "")
        .toLowerCase()
        .includes(normalizedQuery)
    );
  }, [options, query]);

  const emitChange = (nextValue) => {
    onChange({
      target: {
        name,
        value: nextValue,
      },
    });
  };

  const toggleValue = (optionValue) => {
    if (disabled) return;

    if (normalizedValue.includes(optionValue)) {
      emitChange(normalizedValue.filter((item) => item !== optionValue));
      return;
    }

    emitChange([...normalizedValue, optionValue]);
  };

  const removeValue = (optionValue) => {
    emitChange(normalizedValue.filter((item) => item !== optionValue));
  };

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-text-soft">
        {label}
      </label>
      <div className="rounded-2xl border border-border bg-surface p-3 shadow-sm">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-faint" />
          <input
            type="search"
            name={`${name}_search`}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={placeholder || searchPlaceholder}
            className="input-base pl-10"
            disabled={disabled}
          />
        </div>

        {selectedOptions.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => removeValue(option.value)}
                className="inline-flex min-h-9 items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-3 py-1.5 text-sm font-medium text-primary"
                disabled={disabled}
              >
                <span className="max-w-44 truncate">{option.label}</span>
                <X className="h-3.5 w-3.5" />
              </button>
            ))}
          </div>
        )}

        <div className="mt-3 max-h-56 space-y-2 overflow-y-auto rounded-xl border border-border/70 bg-surface-muted/40 p-2">
          {filteredOptions.length > 0 ? (
            filteredOptions.map((option) => {
              const isSelected = normalizedValue.includes(option.value);
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => toggleValue(option.value)}
                  disabled={disabled}
                  className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition ${
                    isSelected
                      ? "bg-primary-soft text-primary"
                      : "text-text-soft hover:bg-surface hover:text-text"
                  }`}
                >
                  <span
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${
                      isSelected
                        ? "border-primary bg-primary text-white"
                        : "border-border bg-surface"
                    }`}
                  >
                    {isSelected && <Check className="h-3.5 w-3.5" />}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{option.label}</span>
                </button>
              );
            })
          ) : (
            <p className="px-2 py-3 text-sm text-text-muted">
              No matches found.
            </p>
          )}
        </div>
      </div>
      <input
        type="hidden"
        name={name}
        value={normalizedValue.join(",")}
        required={required && normalizedValue.length === 0}
      />
      {error && <p className="mt-1 text-sm text-error">{error}</p>}
    </div>
  );
}

export default MultiSelect;
