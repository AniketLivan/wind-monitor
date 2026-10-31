// Shared axis/grid styling so every chart reads as one system.
export const axisProps = {
  stroke: "var(--border)",
  tick: { fill: "var(--text-muted)", fontSize: 11 },
  tickLine: false,
} as const;

export const gridProps = { stroke: "var(--grid)", strokeDasharray: "0", vertical: false } as const;

export function LegendItem({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span style={{ color: dashed ? color : undefined }}>
      <span className={`swatch${dashed ? " dashed" : ""}`} style={dashed ? undefined : { background: color }} />
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
    </span>
  );
}

export const mwTick = (v: number) => `${(v / 1000).toLocaleString("en-GB", { maximumFractionDigits: 1 })} GW`;
