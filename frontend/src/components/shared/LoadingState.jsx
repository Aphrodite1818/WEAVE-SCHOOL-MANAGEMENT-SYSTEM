function LoadingState({ label = "Loading...", fullPage = false }) {
  return (
    <div
      className={`flex w-full items-center justify-center ${fullPage ? "min-h-[55vh]" : "min-h-[260px]"}`}
      role="status"
      aria-label={label}
    >
      <span className="h-12 w-12 animate-spin rounded-full border-[4px] border-primary/20 border-t-primary shadow-sm" />
      <span className="sr-only">{label}</span>
    </div>
  );
}

export default LoadingState;
