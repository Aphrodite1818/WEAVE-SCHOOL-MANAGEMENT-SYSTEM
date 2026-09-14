import { cn } from "../../utils/cn";
import { useId } from "react";

function Input({ label, error, className = "", hint, ...props }) {
  const generatedId = useId();
  const id = props.id || generatedId;
  const errorMessage =
    typeof error === "string"
      ? error
      : error?.message || (error ? JSON.stringify(error) : "");

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-text-soft">
          {label}
        </label>
      )}
      <input className={cn("input-base", className)} {...props} id={id} aria-invalid={Boolean(errorMessage)} aria-describedby={errorMessage || hint ? `${id}-feedback` : props["aria-describedby"]} />
      {hint && !errorMessage && (
        <p id={`${id}-feedback`} className="mt-1.5 text-xs text-text-muted">{hint}</p>
      )}
      {errorMessage && (
        <p id={`${id}-feedback`} role="alert" className="mt-1.5 text-xs font-medium text-error">{errorMessage}</p>
      )}
    </div>
  );
}

export default Input;
