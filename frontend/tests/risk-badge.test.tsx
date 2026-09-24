import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RiskBadge } from "@/components/risk-badge";

describe("RiskBadge", () => {
  it("renders 'Unscored' when there is no risk level yet", () => {
    render(<RiskBadge level={null} />);
    expect(screen.getByText("Unscored")).toBeInTheDocument();
  });

  it("renders the risk level and score", () => {
    render(<RiskBadge level="CRITICAL" score={87.3} />);
    expect(screen.getByText("CRITICAL · 87")).toBeInTheDocument();
  });

  it("renders the risk level without a score suffix when score is omitted", () => {
    render(<RiskBadge level="LOW" />);
    expect(screen.getByText("LOW")).toBeInTheDocument();
  });
});
