type Props = { kind: "loading" | "error" | "empty"; message?: string };

const DEFAULTS = { loading: "Loading…", error: "Something went wrong.", empty: "No data for this selection." };

export function Status({ kind, message }: Props) {
  return (
    <div className={`status status-${kind}`} role={kind === "error" ? "alert" : "status"}>
      {kind === "error" && <strong>Error: </strong>}
      {message ?? DEFAULTS[kind]}
    </div>
  );
}
