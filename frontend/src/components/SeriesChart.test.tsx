import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SeriesChart, forecastLine } from "./SeriesChart";

describe("SeriesChart", () => {
  it("shows the empty status when there are no points", () => {
    render(<SeriesChart points={[]} />);
    expect(screen.getByText("No data for this selection.")).toBeInTheDocument();
  });

  it("renders points with missing forecasts without throwing", () => {
    render(
      <SeriesChart
        points={[
          { time: "2026-01-10T00:00:00Z", actual_mw: 500, forecast_mw: 600, forecast_publish_time: "2026-01-09T07:30:00Z", error_mw: 100 },
          { time: "2026-01-10T00:30:00Z", actual_mw: 510, forecast_mw: null, forecast_publish_time: null, error_mw: null },
        ]}
      />,
    );
    expect(screen.getByText("Actual")).toBeInTheDocument();
    expect(screen.getByText("Forecast")).toBeInTheDocument();
  });
});

describe("forecastLine", () => {
  const pt = (time: string, forecast_mw: number | null) =>
    ({ time, actual_mw: 1, forecast_mw, forecast_publish_time: null, error_mw: null });

  it("keeps hourly slots only, and keeps a genuine missing forecast as a gap (null)", () => {
    const rows = forecastLine([
      pt("2026-01-10T21:00:00Z", 900),
      pt("2026-01-10T21:30:00Z", null),
      pt("2026-01-10T22:00:00Z", null),
      pt("2026-01-10T22:30:00Z", null),
      pt("2026-01-10T23:00:00Z", 950),
    ]);
    expect(rows.map((r) => r.forecast_mw)).toEqual([900, null, 950]);
  });
});
