import { useMemo, useState } from "react";

const COUNTRY_CODE_OPTIONS = [
  { code: "+234", label: "NG" },
  { code: "+233", label: "GH" },
  { code: "+254", label: "KE" },
  { code: "+27", label: "ZA" },
  { code: "+44", label: "UK" },
  { code: "+1", label: "US" },
];

const DEFAULT_COUNTRY_CODE = "+234";
const COUNTRY_CODES_WITH_TRUNK_ZERO = new Set(["+234", "+233", "+254", "+27", "+44"]);

const digitsOnly = (value) => String(value || "").replace(/\D/g, "");
const stripTrunkZero = (countryCode, value) => {
  const digits = digitsOnly(value);
  return COUNTRY_CODES_WITH_TRUNK_ZERO.has(countryCode)
    ? digits.replace(/^0+/, "")
    : digits;
};

function findCountryCode(value) {
  const normalized = String(value || "").trim();
  return COUNTRY_CODE_OPTIONS.find((option) =>
    normalized.startsWith(option.code)
  )?.code;
}

function getLocalNumber(value, countryCode) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "";
  }

  if (normalized.startsWith(countryCode)) {
    return digitsOnly(normalized.slice(countryCode.length));
  }

  const detectedCode = findCountryCode(normalized);
  if (detectedCode) {
    return digitsOnly(normalized.slice(detectedCode.length));
  }

  return stripTrunkZero(countryCode, normalized);
}

function PhoneNumberInput({
  label,
  error,
  name,
  value,
  onChange,
  defaultCountryCode = DEFAULT_COUNTRY_CODE,
  fixedCountryCode = false,
  placeholder = "8012345678",
  className = "",
  ...props
}) {
  const [countryCode, setCountryCode] = useState(
    findCountryCode(value) || defaultCountryCode
  );
  const detectedCountryCode = findCountryCode(value);
  const effectiveCountryCode = fixedCountryCode
    ? defaultCountryCode
    : detectedCountryCode || countryCode;

  const errorMessage =
    typeof error === "string"
      ? error
      : error?.message || (error ? JSON.stringify(error) : "");

  const localNumber = useMemo(
    () => getLocalNumber(value, effectiveCountryCode),
    [effectiveCountryCode, value]
  );

  const emitChange = (nextCountryCode, nextLocalNumber) => {
    const nextDigits = stripTrunkZero(nextCountryCode, nextLocalNumber);
    const nextValue = nextDigits ? `${nextCountryCode}${nextDigits}` : "";

    onChange?.({
      target: {
        name,
        value: nextValue,
      },
    });
  };

  const handleCountryCodeChange = (event) => {
    const nextCountryCode = event.target.value;
    setCountryCode(nextCountryCode);
    emitChange(nextCountryCode, localNumber);
  };

  const handleLocalNumberChange = (event) => {
    const rawValue = event.target.value.trim();
    const pastedCountryCode = findCountryCode(rawValue);

    if (pastedCountryCode) {
      setCountryCode(pastedCountryCode);
      emitChange(pastedCountryCode, getLocalNumber(rawValue, pastedCountryCode));
      return;
    }

    emitChange(effectiveCountryCode, rawValue);
  };

  return (
    <div className="w-full">
      {label && (
        <label className="mb-1.5 block text-sm font-medium text-text-soft">
          {label}
        </label>
      )}
      <div
        className={`flex w-full overflow-hidden rounded-xl border border-border bg-surface-raised transition-all duration-200 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 ${className}`}
      >
        {fixedCountryCode ? (
          <span className="flex w-24 shrink-0 items-center border-r border-border bg-surface-raised px-3 py-2.5 text-sm font-semibold text-text">
            {defaultCountryCode}
          </span>
        ) : (
          <select
            aria-label={`${label || name} country code`}
            value={effectiveCountryCode}
            onChange={handleCountryCodeChange}
            className="w-28 shrink-0 border-r border-border bg-surface-raised px-3 py-2.5 text-sm text-text outline-none"
          >
            {COUNTRY_CODE_OPTIONS.map((option) => (
              <option key={option.code} value={option.code}>
                {option.code} {option.label}
              </option>
            ))}
          </select>
        )}
        <input
          {...props}
          name={name}
          type="tel"
          inputMode="numeric"
          value={localNumber}
          onChange={handleLocalNumberChange}
          placeholder={placeholder}
          className="min-w-0 flex-1 bg-transparent px-4 py-2.5 text-base text-text outline-none placeholder:text-text-muted disabled:cursor-not-allowed disabled:opacity-40 sm:text-sm"
        />
      </div>
      {errorMessage && <p className="mt-1 text-sm text-error">{errorMessage}</p>}
    </div>
  );
}

export default PhoneNumberInput;
