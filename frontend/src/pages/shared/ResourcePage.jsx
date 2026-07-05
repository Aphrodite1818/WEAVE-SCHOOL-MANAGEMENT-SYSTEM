import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import MultiSelect from "../../components/ui/MultiSelect";
import EmptyState from "../../components/shared/EmptyState";
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
  const [isUnavailable, setIsUnavailable] = useState(false);
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
      setIsUnavailable(false);

      try {
        const result = await config.fetchItems(activeFilters, activeContext);
        setItems(asItems(result));
        setTotal(asTotal(result));
      } catch (err) {
        const parsed = parseApiError(
          err,
          `Failed to load ${config.pluralLabel}.`
        );

        if (config.allowUnavailable && parsed.status === 404) {
          setItems([]);
          setTotal(0);
          setIsUnavailable(true);
        } else {
          setError(parsed.message);
        }
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

          if (config.allowUnavailable && parsed.status === 404) {
            setItems([]);
            setTotal(0);
            setIsUnavailable(true);
          } else {
            setError(parsed.message);
          }
          setHasLoadedOnce(true);
          setIsLoading(false);
        }
      }
    };

    loadPage();

    return () => {
      isMounted = false;
    };
  }, [config.allowUnavailable, filters, loadContext, loadItems]);

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
      const payload = config.buildPayload
        ? config.buildPayload(formData, editingItem, context)
        : cleanPayload(formData);

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
    const label = config.getItemLabel ? config.getItemLabel(item, context) : item.id;

    if (!window.confirm(`Delete ${label}? This cannot be undone.`)) {
      return;
    }

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
    }
  };

  const handleRefresh = async () => {
    try {
      const nextContext = await loadContext();
      await loadItems(filters, nextContext);
      showSuccess(`${config.pluralLabel} refreshed successfully.`);
    } catch (err) {
      const parsed = parseApiError(err, "Failed to refresh page data.");

      if (config.allowUnavailable && parsed.status === 404) {
        setItems([]);
        setTotal(0);
        setIsUnavailable(true);
        showError(parsed.message);
      } else {
        showError(parsed.message);
      }
    }
  };

  const clearFilters = () => {
    setFilters(resolveConfig(config.initialFilters, context) || {});
  };

  const showForm =
    !isUnavailable && (config.canCreate || (config.canUpdate && editingItem));
  const unavailableMessage =
    config.unavailableMessage ||
    `${config.pluralLabel} are not available yet.`;
  const isInitialLoading = isLoading && !hasLoadedOnce && !error && !isUnavailable;

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
            <Button variant="outline" onClick={handleRefresh} disabled={isLoading} className="w-full md:w-auto">
              Refresh
            </Button>
          </div>

          {isUnavailable ? (
            <div className="mt-5">
              <EmptyState
                title="Not available"
                description={unavailableMessage}
              />
            </div>
          ) : filterFields.length > 0 && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                loadItems(filters);
              }}
              className="resource-page-filters mt-5 grid gap-3 rounded-2xl border border-border bg-surface-muted/40 p-4 md:grid-cols-3 2xl:grid-cols-4"
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
          )}

          {!isUnavailable && (
            <div className="mt-5 table-wrap">
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
                                  onClick={() => handleDelete(item)}
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
          )}
        </Card>
      </div>
    </div>
  );
}

export default ResourcePage;
