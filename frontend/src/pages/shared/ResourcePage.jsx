import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight, Filter, X } from "lucide-react";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import Modal from "../../components/ui/Modal";
import MultiSelect from "../../components/ui/MultiSelect";
import SearchableSelect from "../../components/ui/SearchableSelect";
import LoadingState from "../../components/shared/LoadingState";
import { getErrorMessage, parseApiError } from "../../services/api";
import { useToast } from "../../hooks/useToast";

const emptyContext = {};

const asItems = (result) => {
  if (Array.isArray(result)) return result;
  return Array.isArray(result?.items) ? result.items : [];
};

const asTotal = (result) => {
  if (Number.isFinite(result?.total)) return result.total;
  if (Array.isArray(result)) return result.length;
  return 0;
};

const resolveConfig = (value, ...args) =>
  typeof value === "function" ? value(...args) : value;

const getInitialForm = (config, context) => ({
  ...(resolveConfig(config.initialForm, context) || {}),
});

const cleanPayload = (payload) =>
  Object.entries(payload).reduce((nextPayload, [key, value]) => {
    nextPayload[key] = value === "" ? null : value;
    return nextPayload;
  }, {});

const payloadValuesEqual = (left, right) => {
  if (Object.is(left, right)) return true;
  if (Array.isArray(left) || Array.isArray(right)) {
    return JSON.stringify(left) === JSON.stringify(right);
  }
  if (
    left &&
    right &&
    typeof left === "object" &&
    typeof right === "object"
  ) {
    return JSON.stringify(left) === JSON.stringify(right);
  }
  return false;
};

const buildPayload = (config, formData, editingItem, context) =>
  config.buildPayload
    ? config.buildPayload(formData, editingItem, context)
    : cleanPayload(formData);

const buildChangedPayload = (config, formData, editingItem, context) => {
  const nextPayload = buildPayload(config, formData, editingItem, context);
  if (!editingItem || !config.mapItemToForm) return nextPayload;

  const originalForm = config.mapItemToForm(editingItem, context);
  const originalPayload = buildPayload(
    config,
    originalForm,
    editingItem,
    context,
  );

  return Object.entries(nextPayload).reduce((changes, [key, value]) => {
    if (!payloadValuesEqual(value, originalPayload[key])) {
      changes[key] = value;
    }
    return changes;
  }, {});
};

function FormControl({ field, value, error, onChange, onValueChange }) {
  const commonProps = {
    name: field.name,
    value: value ?? "",
    onChange,
    required: field.required,
    disabled: field.disabled,
  };

  if (field.type === "select") {
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

  if (field.type === "multiselect") {
    return (
      <MultiSelect
        label={field.label}
        name={field.name}
        value={Array.isArray(value) ? value : []}
        options={field.options || []}
        placeholder={field.placeholder}
        searchPlaceholder={field.searchPlaceholder}
        error={error}
        disabled={field.disabled}
        required={field.required}
        onChange={onChange}
        onValueChange={onValueChange}
      />
    );
  }

  if (field.type === "textarea") {
    return (
      <div>
        <label className="mb-1.5 block text-sm font-medium text-text-soft">
          {field.label}
        </label>
        <textarea
          className="input-base min-h-24"
          placeholder={field.placeholder}
          {...commonProps}
        />
        {error && <p className="mt-1 text-sm text-error">{error}</p>}
      </div>
    );
  }

  return (
    <Input
      label={field.label}
      type={field.type || "text"}
      placeholder={field.placeholder}
      min={field.min}
      max={field.max}
      step={field.step}
      error={error}
      {...commonProps}
    />
  );
}

function ResourcePage({ config }) {
  const { showSuccess, showError } = useToast();
  const [context, setContext] = useState(emptyContext);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [formData, setFormData] = useState(() => getInitialForm(config, emptyContext));
  const [filters, setFilters] = useState(() => resolveConfig(config.initialFilters, emptyContext) || {});
  const [editingItem, setEditingItem] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [isFilterSheetOpen, setIsFilterSheetOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const contextRef = useRef(context);
  const filtersRef = useRef(filters);
  const editingItemRef = useRef(editingItem);

  useEffect(() => {
    contextRef.current = context;
  }, [context]);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  useEffect(() => {
    editingItemRef.current = editingItem;
  }, [editingItem]);

  const fields = useMemo(
    () => resolveConfig(config.fields, context, editingItem) || [],
    [config, context, editingItem]
  );
  const filterFields = useMemo(
    () => resolveConfig(config.filters, context) || [],
    [config, context]
  );
  const columns = useMemo(
    () => resolveConfig(config.columns, context) || [],
    [config, context]
  );

  const resetForm = useCallback(() => {
    setEditingItem(null);
    setFormData(getInitialForm(config, context));
    setFieldErrors({});
  }, [config, context]);

  const loadContext = useCallback(async () => {
    if (!config.loadContext) return emptyContext;
    const nextContext = await config.loadContext();
    const resolvedContext = nextContext || emptyContext;
    contextRef.current = resolvedContext;
    setContext(resolvedContext);
    setFormData((current) =>
      editingItemRef.current ? current : getInitialForm(config, resolvedContext)
    );
    return resolvedContext;
  }, [config]);

  const loadItems = useCallback(
    async (
      activeFilters = filtersRef.current,
      activeContext = contextRef.current
    ) => {
      setIsLoading(true);
      setError(null);

      try {
        const result = await config.fetchItems(activeFilters, activeContext);
        setItems(asItems(result));
        setTotal(asTotal(result));
      } catch (err) {
        const parsed = parseApiError(
          err,
          `Failed to load ${config.pluralLabel}.`
        );

        setError(parsed.message);
      } finally {
        setHasLoadedOnce(true);
        setIsLoading(false);
      }
    },
    [config]
  );

  useEffect(() => {
    let isMounted = true;

    const loadPage = async () => {
      try {
        const nextContext = await loadContext();
        if (isMounted) {
          await loadItems(filters, nextContext);
        }
      } catch (err) {
        if (isMounted) {
          const parsed = parseApiError(err, "Failed to load page data.");

          setError(parsed.message);
          setHasLoadedOnce(true);
          setIsLoading(false);
        }
      }
    };

    loadPage();

    return () => {
      isMounted = false;
    };
  }, [filters, loadContext, loadItems]);

  const updateFormValue = (name, nextValue) => {
    setFormData((current) => ({ ...current, [name]: nextValue }));
    setFieldErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleFormChange = (event) => {
    const { multiple, name, selectedOptions, value } = event.target;
    const nextValue = multiple
      ? Array.from(selectedOptions, (option) => option.value)
      : value;

    updateFormValue(name, nextValue);
  };

  const handleFilterChange = (event) => {
    const { name, value } = event.target;
    setFilters((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    setFieldErrors({});
    let submitSucceeded = false;

    try {
      const payload = editingItem
        ? buildChangedPayload(config, formData, editingItem, context)
        : buildPayload(config, formData, editingItem, context);

      if (editingItem && Object.keys(payload).length === 0) {
        showSuccess("No changes to save.");
        resetForm();
        return;
      }

      if (editingItem) {
        const result = await config.updateItem(editingItem.id, payload);
        showSuccess(
          config.buildSuccessMessage
            ? config.buildSuccessMessage({
                action: "update",
                result,
                payload,
                item: editingItem,
                context,
              })
            : `${config.singularLabel} updated successfully.`
        );
      } else {
        const result = await config.createItem(payload);
        showSuccess(
          config.buildSuccessMessage
            ? config.buildSuccessMessage({
                action: "create",
                result,
                payload,
                context,
              })
            : `${config.singularLabel} created successfully.`
        );
      }

      resetForm();
      submitSucceeded = true;
    } catch (err) {
      const parsed = parseApiError(
        err,
        editingItem
          ? `Failed to update ${config.singularLabel.toLowerCase()}.`
          : `Failed to create ${config.singularLabel.toLowerCase()}.`
      );
      setFieldErrors(parsed.fieldErrors);
      showError(parsed.message);
    } finally {
      setIsSubmitting(false);
    }

    if (submitSucceeded) {
      try {
        await loadItems();
      } catch (err) {
        const parsed = parseApiError(
          err,
          `Saved ${config.singularLabel.toLowerCase()} but failed to refresh the list.`
        );
        showError(parsed.message);
      }
    }
  };

  const handleEdit = (item) => {
    setEditingItem(item);
    setFormData(config.mapItemToForm(item, context));
    setFieldErrors({});
  };

  const handleDelete = async (item) => {
    if (!item) return;
    setBusyId(item.id);

    try {
      await config.deleteItem(item.id);
      if (editingItem?.id === item.id) resetForm();
      showSuccess(`${config.singularLabel} deleted successfully.`);
      await loadItems();
    } catch (err) {
      const message = getErrorMessage(err, `Failed to delete ${config.singularLabel.toLowerCase()}.`);
      showError(message);
    } finally {
      setBusyId(null);
      setDeleteTarget(null);
    }
  };

  const clearFilters = () => {
    setFilters(resolveConfig(config.initialFilters, context) || {});
  };

  const applyFilters = async () => {
    await loadItems(filters);
    setIsFilterSheetOpen(false);
  };

  const searchableField = filterFields.find((field) => field.name === "search");
  const sheetFilterFields = filterFields.filter((field) => field.name !== "search");
  const hasNonSearchFilters = sheetFilterFields.length > 0;

  const showForm = config.canCreate || (config.canUpdate && editingItem);
  const isInitialLoading = isLoading && !hasLoadedOnce && !error;

  if (isInitialLoading) {
    return <LoadingState label={`Loading ${config.pluralLabel.toLowerCase()}...`} fullPage />;
  }

  return (
    <div className="resource-page-shell w-full max-w-none space-y-5 sm:mx-auto sm:max-w-7xl">
      {error && (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {error}
        </div>
      )}
      <div className={`resource-page-grid grid w-full min-w-0 gap-5 ${showForm ? "2xl:grid-cols-[minmax(320px,420px)_minmax(0,1fr)]" : ""}`}>
        {showForm && (
          <Card className="resource-page-form-card p-4 sm:p-5 2xl:sticky 2xl:top-28 2xl:self-start">
            <h2 className="text-lg font-semibold">
              {editingItem ? `Edit ${config.singularLabel.toLowerCase()}` : `Create ${config.singularLabel.toLowerCase()}`}
            </h2>
            {config.formHelp && (
              <p className="mt-1 text-sm text-text-muted">{config.formHelp}</p>
            )}

            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              {fields
                .filter((field) => !field.hidden)
                .filter((field) => (editingItem ? field.showOnEdit !== false : field.showOnCreate !== false))
                .map((field) => (
                  <FormControl
                    key={field.name}
                    field={field}
                    value={formData[field.name]}
                    error={fieldErrors[field.name]}
                    onChange={handleFormChange}
                    onValueChange={updateFormValue}
                  />
                ))}

              <div className="grid gap-2 sm:flex sm:flex-wrap">
                <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
                  {isSubmitting ? "Saving..." : editingItem ? "Save changes" : "Create"}
                </Button>
                {editingItem && (
                  <Button type="button" variant="outline" onClick={resetForm} className="w-full sm:w-auto">
                    Cancel
                  </Button>
                )}
              </div>
            </form>
          </Card>
        )}

        <Card className="resource-page-list-card p-4 sm:p-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 className="text-lg font-semibold">{config.pluralLabel}</h2>
              <p className="mt-1 text-sm text-text-muted">
                {total} record{total === 1 ? "" : "s"} found.
              </p>
            </div>
          </div>

          {filterFields.length > 0 && (
            <>
              <div className="mt-5 flex items-end gap-2 md:hidden">
                {searchableField ? (
                  <FormControl
                    field={{ ...searchableField, label: "" }}
                    value={filters[searchableField.name]}
                    onChange={handleFilterChange}
                    onValueChange={() => {}}
                  />
                ) : null}
                {hasNonSearchFilters ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => setIsFilterSheetOpen(true)}
                    aria-label="Open filters"
                    className="shrink-0"
                  >
                    <Filter className="h-4 w-4" />
                  </Button>
                ) : null}
                <Button type="button" size="icon" onClick={applyFilters} aria-label="Apply search" className="shrink-0">
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>

              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  loadItems(filters);
                }}
                className="resource-page-filters mt-5 hidden gap-3 rounded-2xl border border-border bg-surface-muted/40 p-4 md:grid md:grid-cols-3 2xl:grid-cols-4"
              >
                {filterFields.map((field) => (
                  <FormControl
                    key={field.name}
                    field={field}
                    value={filters[field.name]}
                    onChange={handleFilterChange}
                    onValueChange={() => {}}
                  />
                ))}
                <div className="grid gap-2 sm:flex sm:items-end">
                  <Button type="submit" size="small" className="w-full sm:w-auto">
                    Apply
                  </Button>
                  <Button type="button" variant="outline" size="small" onClick={clearFilters} className="w-full sm:w-auto">
                    Clear
                  </Button>
                </div>
              </form>
            </>
          )}

          <>
            <div className="resource-page-mobile-list mobile-scroll-list mt-5 grid gap-2 md:hidden">
              {items.length === 0 ? (
                <div className="rounded-xl border border-border bg-surface-muted/30 px-4 py-5 text-sm text-text-muted">
                  No records found.
                </div>
              ) : (
                items.map((item) => {
                  const primaryColumn = columns[0];
                  const secondaryColumns = columns.slice(1, 3);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => (config.canUpdate ? handleEdit(item) : undefined)}
                      className="w-full rounded-xl border border-border bg-surface px-3 py-3 text-left shadow-sm transition hover:bg-surface-muted/40"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-text">
                            {primaryColumn?.render ? primaryColumn.render(item, context) : item[primaryColumn?.key] || "-"}
                          </p>
                          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-muted">
                            {secondaryColumns.map((column) => (
                              <span key={column.key} className="max-w-full truncate">
                                {column.render ? column.render(item, context) : item[column.key] || "-"}
                              </span>
                            ))}
                          </div>
                        </div>
                        {(config.canUpdate || config.canDelete) && <ChevronRight className="h-4 w-4 shrink-0 text-text-muted" />}
                      </div>
                      {(config.canUpdate || config.canDelete) && (
                        <div className="mt-3 flex gap-2">
                          {config.canUpdate && (
                            <span className="rounded-lg border border-border px-2.5 py-1 text-xs font-semibold text-text-soft">
                              Tap to edit
                            </span>
                          )}
                          {config.canDelete && (
                            <Button
                              type="button"
                              variant="danger"
                              size="xs"
                              onClick={(event) => {
                                event.stopPropagation();
                                setDeleteTarget(item);
                              }}
                              disabled={busyId === item.id}
                              className="ml-auto"
                            >
                              {busyId === item.id ? "Deleting..." : "Delete"}
                            </Button>
                          )}
                        </div>
                      )}
                    </button>
                  );
                })
              )}
            </div>

            <div className="table-wrap mt-5 hidden md:block">
              <table className="data-table">
                <thead>
                  <tr>
                    {columns.map((column) => (
                      <th key={column.key}>
                        {column.label}
                      </th>
                    ))}
                    {(config.canUpdate || config.canDelete) && (
                      <th>Actions</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td
                        colSpan={columns.length + 1}
                        className="text-text-muted"
                      >
                        <span>No records found.</span>
                      </td>
                    </tr>
                  ) : (
                    items.map((item) => (
                      <tr key={item.id}>
                        {columns.map((column) => (
                          <td key={column.key} data-label={column.label}>
                            <span>{column.render ? column.render(item, context) : item[column.key] || "-"}</span>
                          </td>
                        ))}
                        {(config.canUpdate || config.canDelete) && (
                          <td data-label="Actions">
                            <div className="grid w-full gap-2 sm:flex sm:flex-wrap md:w-auto">
                              {config.canUpdate && (
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="small"
                                  onClick={() => handleEdit(item)}
                                  disabled={busyId === item.id}
                                  className="w-full sm:w-auto"
                                >
                                  Edit
                                </Button>
                              )}
                              {config.canDelete && (
                                <Button
                                  type="button"
                                  variant="danger"
                                  size="small"
                                  onClick={() => setDeleteTarget(item)}
                                  disabled={busyId === item.id}
                                  className="w-full sm:w-auto"
                                >
                                  {busyId === item.id ? "Deleting..." : "Delete"}
                                </Button>
                              )}
                            </div>
                          </td>
                        )}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </>
        </Card>
      </div>

      {isFilterSheetOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end bg-slate-950/35 px-3 pb-3 pt-16 backdrop-blur-sm md:hidden"
          onClick={() => setIsFilterSheetOpen(false)}
        >
          <div
            className="w-full rounded-2xl border border-border bg-surface p-4 shadow-premium"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold">Filters</h2>
              <Button type="button" variant="ghost" size="icon" onClick={() => setIsFilterSheetOpen(false)} aria-label="Close filters">
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="grid gap-3">
              {sheetFilterFields.map((field) => (
                <FormControl
                  key={field.name}
                  field={field}
                  value={filters[field.name]}
                  onChange={handleFilterChange}
                  onValueChange={() => {}}
                />
              ))}
              <div className="grid grid-cols-2 gap-2 pt-1">
                <Button type="button" variant="outline" onClick={clearFilters}>
                  Clear
                </Button>
                <Button type="button" onClick={applyFilters}>
                  Apply
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
      <Modal
        open={Boolean(deleteTarget)}
        title={`Delete ${config.singularLabel.toLowerCase()}`}
        description={
          deleteTarget
            ? `Delete ${config.getItemLabel ? config.getItemLabel(deleteTarget, context) : deleteTarget.id}? This cannot be undone.`
            : ""
        }
        onClose={() => !busyId && setDeleteTarget(null)}
        closeOnOverlay={!busyId}
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" disabled={Boolean(busyId)} onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button type="button" variant="danger" disabled={Boolean(busyId)} onClick={() => handleDelete(deleteTarget)}>
              {busyId ? "Deleting..." : "Delete"}
            </Button>
          </div>
        }
      >
        <p className="text-sm leading-6 text-text-muted">
          This action permanently removes the record from this workspace.
        </p>
      </Modal>
    </div>
  );
}

export default ResourcePage;
