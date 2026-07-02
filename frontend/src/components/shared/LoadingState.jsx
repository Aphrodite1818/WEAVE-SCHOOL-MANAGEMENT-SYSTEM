function LoadingState({ label = "Loading..." }) {
  return (
    <div className="flex min-h-44 items-center justify-center rounded-2xl border border-border bg-surface" role="status" aria-label={label}>
      <span className="h-8 w-8 animate-spin rounded-full border-[3px] border-primary/20 border-t-primary shadow-sm" />
      <span className="sr-only">{label}</span>
    </div>
  );
}

export default LoadingState;
