const mw = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });

export const formatMw = (v: number | null | undefined): string =>
  v == null || !Number.isFinite(v) ? "—" : `${mw.format(v)} MW`;

export const formatPct = (v: number | null | undefined): string =>
  v == null || !Number.isFinite(v) ? "—" : `${v.toFixed(1)}%`;

// January is GMT, so UK time equals UTC; format in Europe/London so that stays true for any range.
const dt = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
});
const day = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", day: "2-digit", month: "short" });

export const formatTime = (iso: string | null | undefined): string => (iso ? dt.format(new Date(iso)) : "—");
export const formatDay = (iso: string): string => day.format(new Date(iso));
