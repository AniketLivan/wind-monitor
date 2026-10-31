import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Metrics } from "../types";
import { StatCards } from "./StatCards";

const empty: Metrics = {
  n: 0, mae: null, rmse: null, bias: null, nmae_pct: null, p50_abs: null, p90_abs: null,
  p99_abs: null, p90_shortfall: null, max_over: null, max_under: null, pct_over: null, pct_under: null,
};

describe("StatCards", () => {
  it("labels a positive bias as over-forecast", () => {
    render(<StatCards metrics={{ ...empty, n: 4, mae: 87.5, bias: 62.5, nmae_pct: 8.75, p90_shortfall: 170 }} />);
    expect(screen.getByText(/over-forecast/i)).toBeInTheDocument();
    expect(screen.getByText("Typical miss (MAE)")).toBeInTheDocument();
    expect(screen.getByText("P90 shortfall buffer")).toBeInTheDocument();
  });

  it("renders dashes, never NaN, when there is no data", () => {
    const { container } = render(<StatCards metrics={empty} />);
    expect(container.textContent).not.toContain("NaN");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });
});
