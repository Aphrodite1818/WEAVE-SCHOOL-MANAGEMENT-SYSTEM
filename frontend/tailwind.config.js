/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "rgb(var(--color-background) / <alpha-value>)",
        surface: {
          DEFAULT: "rgb(var(--color-surface) / <alpha-value>)",
          raised: "rgb(var(--color-surface-raised) / <alpha-value>)",
          muted: "rgb(var(--color-surface-muted) / <alpha-value>)",
          subtle: "rgb(var(--color-surface-subtle) / <alpha-value>)",
          tint: "rgb(var(--color-surface-tint) / <alpha-value>)",
          blue: "rgb(var(--color-surface-blue) / <alpha-value>)",
          emerald: "rgb(var(--color-surface-emerald) / <alpha-value>)",
          amber: "rgb(var(--color-surface-amber) / <alpha-value>)",
          rose: "rgb(var(--color-surface-rose) / <alpha-value>)",
        },
        border: {
          DEFAULT: "rgb(var(--color-border) / <alpha-value>)",
          strong: "rgb(var(--color-border-strong) / <alpha-value>)",
          subtle: "rgb(var(--color-border-subtle) / <alpha-value>)",
        },
        text: {
          DEFAULT: "rgb(var(--color-text) / <alpha-value>)",
          soft: "rgb(var(--color-text-soft) / <alpha-value>)",
          muted: "rgb(var(--color-text-muted) / <alpha-value>)",
          faint: "rgb(var(--color-text-faint) / <alpha-value>)",
          inverse: "rgb(var(--color-text-inverse) / <alpha-value>)",
        },
        primary: {
          DEFAULT: "#2563EB",
          hover: "#1D4ED8",
          soft: "#DBEAFE",
          subtle: "#EFF6FF",
          deep: "#1E3A8A",
        },
        secondary: {
          DEFAULT: "#1E293B",
          hover: "#0F172A",
          soft: "#F1F5F9",
        },
        accent: {
          DEFAULT: "#4F46E5",
          hover: "#4338CA",
          soft: "#E0E7FF",
        },
        success: {
          DEFAULT: "#10B981",
          hover: "#059669",
          soft: "#D1FAE5",
        },
        warning: {
          DEFAULT: "#F59E0B",
          hover: "#D97706",
          soft: "#FEF3C7",
        },
        error: {
          DEFAULT: "#E11D48",
          hover: "#BE123C",
          soft: "#FFE4E6",
        },
      },
      boxShadow: {
        premium:
          "0 1px 2px rgba(15, 23, 42, 0.04), 0 20px 50px rgba(15, 23, 42, 0.07)",
        "premium-hover":
          "0 2px 6px rgba(15, 23, 42, 0.06), 0 24px 60px rgba(15, 23, 42, 0.1)",
        "inner-soft": "inset 0 1px 2px rgba(15, 23, 42, 0.04)",
        "soft-card": "0 8px 30px rgba(15, 23, 42, 0.06)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
