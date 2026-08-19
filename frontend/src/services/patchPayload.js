const valuesEqual = (left, right) => {
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

export const asItems = (result) => {
  if (Array.isArray(result)) return result;
  return Array.isArray(result?.items) ? result.items : [];
};

export const rememberById = (cache, result) => {
  asItems(result).forEach((item) => {
    if (item?.id) cache.set(String(item.id), item);
  });
  return result;
};

export const rememberRecord = (cache, record) => {
  if (record?.id) cache.set(String(record.id), record);
  return record;
};

export const buildChangedPatch = (current, payload = {}) =>
  Object.entries(payload).reduce((changes, [key, value]) => {
    // Undefined means the caller did not provide a JSON value. Never convert it
    // into an update intent; explicit null remains available for clearable fields.
    if (value === undefined) return changes;

    if (!current || !valuesEqual(value, current[key])) {
      changes[key] = value;
    }
    return changes;
  }, {});

export const mergePatchResult = (current, changes, response) => ({
  ...(current || {}),
  ...changes,
  ...(response || {}),
});

export const hasPatchChanges = (payload) => Object.keys(payload || {}).length > 0;
