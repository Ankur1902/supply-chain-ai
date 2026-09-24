import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(value: number, maximumFractionDigits = 0): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(value);
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPercent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatDate(value: string | Date): string {
  const d = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(d);
}

export function formatDateTime(value: string | Date): string {
  const d = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

/** SHAP feature values for numeric features (e.g. a delay-rate like
 * "0.30987654321") come through as raw string reprs — round any
 * float-looking string to a readable precision rather than showing full
 * floating-point noise. Non-numeric values (category names) pass through. */
export function formatFeatureValue(value: string): string {
  const n = Number(value);
  if (Number.isNaN(n) || value.trim() === "") return value;
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}
