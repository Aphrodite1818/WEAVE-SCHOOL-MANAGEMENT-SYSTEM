import { cn } from "../../utils/cn";

const variantStyles = {
  primary: "bg-gradient-to-b from-primary/90 to-primary text-primary-foreground shadow-sm shadow-primary/20 hover:from-primary hover:to-primary-hover border border-primary/20",
  secondary: "bg-gradient-to-b from-secondary/90 to-secondary text-text-inverse shadow-sm hover:from-secondary hover:to-secondary-hover border border-secondary/20",
  accent: "bg-gradient-to-b from-accent/90 to-accent text-accent-foreground shadow-sm shadow-accent/20 hover:from-accent hover:to-accent-hover border border-accent/20",
  outline: "border border-border/80 bg-surface text-text-soft shadow-sm hover:border-border hover:bg-surface-muted/50 hover:text-text",
  ghost: "bg-transparent text-text-soft hover:bg-surface-muted/50 hover:text-text",
  danger: "bg-gradient-to-b from-error/90 to-error text-text-inverse shadow-sm hover:from-error hover:to-error-hover border border-error/20",
  success: "bg-gradient-to-b from-success/90 to-success text-text-inverse shadow-sm hover:from-success hover:to-success-hover border border-success/20",
};

const sizeStyles = {
  xs: "min-h-8 rounded-lg px-2.5 py-1.5 text-xs",
  sm: "min-h-9 rounded-lg px-3 py-1.5 text-xs",
  small: "min-h-9 rounded-lg px-3 py-1.5 text-xs",
  medium: "min-h-10 px-4 py-2 text-sm",
  large: "min-h-12 rounded-2xl px-5 py-3 text-base",
  icon: "h-10 w-10 rounded-xl !p-0",
};

function Button({
  children,
  variant = "primary",
  size = "medium",
  className = "",
  type = "button",
  ...props
}) {
  return (
    <button
      type={type}
      className={cn(
        "btn-base",
        variantStyles[variant] || variantStyles.primary,
        sizeStyles[size] || sizeStyles.medium,
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export default Button;
