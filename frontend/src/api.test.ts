import { afterEach, describe, expect, it, vi } from "vitest";
import { buildQuery, fetchMetrics } from "./api";
import type { Selection } from "./types";

const sel: Selection = { start: "2026-01-02", end: "2026-02-01", mode: "day_ahead", horizonH: 4 };

describe("buildQuery", () => {
  it("omits horizon_h in day-ahead mode", () => {
    expect(buildQuery(sel)).toBe("start=2026-01-02&end=2026-02-01&mode=day_ahead");
  });

  it("includes horizon_h in horizon mode", () => {
    expect(buildQuery({ ...sel, mode: "horizon" })).toBe(
      "start=2026-01-02&end=2026-02-01&mode=horizon&horizon_h=4",
    );
  });
});

describe("fetchMetrics", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("rejects with the API's detail message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: "start must be on or before end" }), { status: 422 }),
      ),
    );
    await expect(fetchMetrics(sel)).rejects.toThrow("start must be on or before end");
  });

  it("explains a gateway error as the backend being unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>Bad Gateway</html>", { status: 502 })));
    await expect(fetchMetrics(sel)).rejects.toThrow("Cannot reach the server");
  });
});
