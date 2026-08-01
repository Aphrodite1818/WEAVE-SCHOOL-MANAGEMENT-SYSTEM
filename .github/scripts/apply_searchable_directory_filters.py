from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8")
    if old not in content:
        raise RuntimeError(f"Expected block not found in {path}: {old[:100]!r}")
    file_path.write_text(content.replace(old, new, 1), encoding="utf-8")


replace_once(
    "frontend/src/pages/shared/ResourcePage.jsx",
    'import MultiSelect from "../../components/ui/MultiSelect";\n',
    'import MultiSelect from "../../components/ui/MultiSelect";\n'
    'import SearchableSelect from "../../components/ui/SearchableSelect";\n',
)
replace_once(
    "frontend/src/pages/shared/ResourcePage.jsx",
    '''  if (field.type === "select") {
    return (
      <div>
        <label className="mb-1.5 block text-sm font-medium text-text-soft">
          {field.label}
        </label>
        <select className="input-base" {...commonProps}>
          <option value="">{field.placeholder || "Select an option"}</option>
          {(field.options || []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {error && <p className="mt-1 text-sm text-error">{error}</p>}
      </div>
    );
  }
''',
    '''  if (field.type === "select") {
    return (
      <SearchableSelect
        label={field.label}
        name={field.name}
        value={value ?? ""}
        options={field.options || []}
        placeholder={field.placeholder || "Select an option"}
        searchPlaceholder={
          field.searchPlaceholder || `Search ${String(field.label || "options").toLowerCase()}`
        }
        searchable={field.searchable !== false}
        clearable={field.clearable !== false && !field.required}
        disabled={field.disabled}
        required={field.required}
        error={error}
        onChange={(nextValue) =>
          onChange({
            target: {
              name: field.name,
              value: nextValue,
              multiple: false,
              selectedOptions: [],
            },
          })
        }
      />
    );
  }
''',
)

replace_once(
    "frontend/src/pages/admin/StudentDirectoryPage.jsx",
    'import Modal from "../../components/ui/Modal";\n',
    'import Modal from "../../components/ui/Modal";\n'
    'import SearchableSelect from "../../components/ui/SearchableSelect";\n',
)
replace_once(
    "frontend/src/pages/admin/StudentDirectoryPage.jsx",
    '''function SelectField({ label, name, value, onChange, options, placeholder, error, required }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-text-soft">{label}</span>
      <select
        className="input-base"
        name={name}
        value={value || ""}
        onChange={onChange}
        required={required}
      >
        <option value="">{placeholder || "Select"}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error ? <span className="mt-1 block text-xs text-error">{error}</span> : null}
    </label>
  );
}
''',
    '''function SelectField({
  label,
  name,
  value,
  onChange,
  options,
  placeholder,
  error,
  required,
  searchable = true,
}) {
  return (
    <SearchableSelect
      label={label}
      name={name}
      value={value || ""}
      options={options}
      placeholder={placeholder || "Select"}
      searchPlaceholder={`Search ${String(label || "options").toLowerCase()}`}
      searchable={searchable}
      clearable={!required}
      required={required}
      error={error}
      onChange={(nextValue) =>
        onChange({
          target: {
            name,
            value: nextValue,
          },
        })
      }
    />
  );
}
''',
)

print("Searchable resource and student-directory filters applied.")
