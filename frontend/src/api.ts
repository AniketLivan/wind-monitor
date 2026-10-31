import type { ByHorizonResponse, Meta, MetricsResponse, Selection, SeriesResponse } from "./types";

export class ApiError extends Error {}

export function buildQuery(sel: Selection): string {
  const q = new URLSearchParams({ start: sel.start, end: sel.end, mode: sel.mode });
  if (sel.mode === "horizon") q.set("horizon_h", String(sel.horizonH));
  return q.toString();
}

const UNREACHABLE = "Cannot reach the server. Is the backend running?";

async function get<T>(path: string): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(path);
  } catch {
    throw new ApiError(UNREACHABLE);
  }
  // 502-504 come from the proxy when the backend is down or restarting.
  if (resp.status >= 502 && resp.status <= 504) throw new ApiError(UNREACHABLE);
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail);
  }
  return resp.json() as Promise<T>;
}

export const fetchMeta = () => get<Meta>("/api/meta");
export const fetchSeries = (sel: Selection) => get<SeriesResponse>(`/api/series?${buildQuery(sel)}`);
export const fetchMetrics = (sel: Selection) => get<MetricsResponse>(`/api/metrics?${buildQuery(sel)}`);
export const fetchByHorizon = (start: string, end: string) =>
  get<ByHorizonResponse>(`/api/metrics/by-horizon?${new URLSearchParams({ start, end })}`);
