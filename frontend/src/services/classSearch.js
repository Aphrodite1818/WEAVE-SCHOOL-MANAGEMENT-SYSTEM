const normalizeSearchText = (value) =>
  String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");

const compactSearchText = (value) =>
  normalizeSearchText(value).replace(/[^a-z0-9]/g, "");

const isSubsequence = (query, value) => {
  if (!query) return true;
  let queryIndex = 0;
  for (const character of value) {
    if (character === query[queryIndex]) queryIndex += 1;
    if (queryIndex === query.length) return true;
  }
  return false;
};

const classSearchHaystacks = (item) => {
  const label = [item?.name, item?.arm].filter(Boolean).join(" ");
  return [item?.name, item?.arm, label]
    .filter(Boolean)
    .map((value) => ({
      normalized: normalizeSearchText(value),
      compact: compactSearchText(value),
    }));
};

export const filterClasses = (items, search) => {
  const normalizedSearch = normalizeSearchText(search);
  const compactSearch = compactSearchText(search);
  if (!normalizedSearch) return items;

  const exactArmMatches = items.filter(
    (item) => compactSearchText(item?.arm) === compactSearch,
  );
  if (compactSearch.length === 1 && exactArmMatches.length > 0) {
    return exactArmMatches;
  }

  return items.filter((item) =>
    classSearchHaystacks(item).some(({ normalized, compact }) => {
      if (normalized.includes(normalizedSearch)) return true;
      if (compact.includes(compactSearch)) return true;
      return compactSearch.length >= 2 && isSubsequence(compactSearch, compact);
    }),
  );
};
