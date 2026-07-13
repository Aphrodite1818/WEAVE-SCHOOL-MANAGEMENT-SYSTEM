import { useId } from "react";

function WeaveIcon({ className = "h-10 w-10", title = "Weave", decorative = false }) {
  const generatedTitleId = useId();
  const titleId = decorative ? undefined : `weave-icon-title-${generatedTitleId}`;

  return (
    <svg
      className={className}
      viewBox="0 0 140 140"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role={decorative ? "presentation" : "img"}
      aria-hidden={decorative ? "true" : undefined}
      aria-labelledby={titleId}
      focusable="false"
    >
      {decorative ? null : <title id={titleId}>{title}</title>}
      <path
        d="M14 46C42 46 42 94 70 94C98 94 98 46 126 46"
        stroke="var(--weave-icon-primary, #1D4ED8)"
        strokeWidth="18"
        strokeLinecap="round"
      />
      <path
        d="M14 94C42 94 42 46 70 46C98 46 98 94 126 94"
        stroke="var(--weave-icon-accent, #F59E0B)"
        strokeWidth="18"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default WeaveIcon;
