import { describe, expect, it } from "vitest";

import { cn, formatCurrency, formatFeatureValue, formatPercent } from "@/lib/utils";

describe("cn", () => {
  it("merges class names and resolves Tailwind conflicts", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
    expect(cn("text-sm", undefined, "font-bold")).toBe("text-sm font-bold");
  });
});

describe("formatCurrency", () => {
  it("formats as whole-dollar USD", () => {
    expect(formatCurrency(1234.56)).toBe("$1,235");
    expect(formatCurrency(0)).toBe("$0");
  });
});

describe("formatPercent", () => {
  it("converts a fraction to a percentage string", () => {
    expect(formatPercent(0.3012)).toBe("30.1%");
    expect(formatPercent(0.5, 0)).toBe("50%");
  });
});

describe("formatFeatureValue", () => {
  it("rounds a long float string to a readable precision", () => {
    expect(formatFeatureValue("0.30987654321")).toBe("0.31");
  });

  it("passes through integers unchanged", () => {
    expect(formatFeatureValue("4")).toBe("4");
  });

  it("passes through non-numeric category values unchanged", () => {
    expect(formatFeatureValue("Standard Class")).toBe("Standard Class");
  });
});
