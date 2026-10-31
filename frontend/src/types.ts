// Mirrors the backend JSON (backend/app/api.py).

export type Mode = "day_ahead" | "horizon";

export type Selection = { start: string; end: string; mode: Mode; horizonH: number };

export type SeriesPoint = {
  time: string;
  actual_mw: number;
  forecast_mw: number | null;
  forecast_publish_time: string | null;
  error_mw: number | null;
};

export type SeriesResponse = {
  mode: Mode;
  horizon_h: number | null;
  cutoff: string | null;
  points: SeriesPoint[];
};

export type Extreme = { error_mw: number; start_time: string };

export type Metrics = {
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  nmae_pct: number | null;
  p50_abs: number | null;
  p90_abs: number | null;
  p99_abs: number | null;
  p90_shortfall: number | null;
  max_over: Extreme | null;
  max_under: Extreme | null;
  pct_over: number | null;
  pct_under: number | null;
};

export type Bin = { lo_mw: number; hi_mw: number; count: number };

export type MetricsResponse = { mode: Mode; horizon_h: number | null; metrics: Metrics; histogram: Bin[] };

export type HorizonSummary = {
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  p90_shortfall: number | null;
};

export type ByHorizonResponse = {
  horizons: (HorizonSummary & { horizon_h: number })[];
  day_ahead: HorizonSummary;
};

export type Meta = {
  scope: { start_date: string; end_date: string };
  day_ahead_cutoff: string;
  max_horizon_h: number;
  actuals: { count: number; first: string | null; last: string | null };
  forecasts: { runs: number; first_publish: string | null; last_publish: string | null };
  last_ingest_at: string | null;
};
