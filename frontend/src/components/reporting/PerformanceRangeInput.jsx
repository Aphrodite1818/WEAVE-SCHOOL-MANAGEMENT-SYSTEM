function clampScore(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.min(100, Math.max(0, numeric));
}

function PerformanceRangeInput({ minimum, maximum, onChange, disabled = false }) {
  const min = clampScore(minimum);
  const max = clampScore(maximum);

  const updateMinimum = (value) => {
    const next = Math.min(clampScore(value), max);
    onChange({ minimum: next, maximum: max });
  };
  const updateMaximum = (value) => {
    const next = Math.max(clampScore(value), min);
    onChange({ minimum: min, maximum: next });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text-soft">Performance range</p>
          <p className="text-xs text-text-muted">Inclusive: {min}% through {max}%.</p>
        </div>
        <span className="rounded-full border border-border bg-surface-muted/40 px-3 py-1 text-xs font-semibold text-text">
          {min}% – {max}%
        </span>
      </div>

      <div className="relative grid h-8 items-center">
        <div className="col-start-1 row-start-1 h-1.5 rounded-full bg-surface-muted" />
        <div
          className="col-start-1 row-start-1 h-1.5 rounded-full bg-primary/60"
          style={{ marginLeft: `${min}%`, width: `${Math.max(0, max - min)}%` }}
        />
        <input
          aria-label="Minimum performance percentage"
          type="range"
          min="0"
          max="100"
          step="1"
          value={min}
          disabled={disabled}
          onChange={(event) => updateMinimum(event.target.value)}
          className="col-start-1 row-start-1 w-full bg-transparent accent-primary"
        />
        <input
          aria-label="Maximum performance percentage"
          type="range"
          min="0"
          max="100"
          step="1"
          value={max}
          disabled={disabled}
          onChange={(event) => updateMaximum(event.target.value)}
          className="col-start-1 row-start-1 w-full bg-transparent accent-primary"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-text-muted">
            Minimum %
          </span>
          <input
            type="number"
            min="0"
            max={max}
            step="1"
            value={min}
            disabled={disabled}
            className="input-base"
            onChange={(event) => updateMinimum(event.target.value)}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-text-muted">
            Maximum %
          </span>
          <input
            type="number"
            min={min}
            max="100"
            step="1"
            value={max}
            disabled={disabled}
            className="input-base"
            onChange={(event) => updateMaximum(event.target.value)}
          />
        </label>
      </div>
    </div>
  );
}

export default PerformanceRangeInput;
