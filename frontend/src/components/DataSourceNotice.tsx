import { useResumeStore } from "../store/useResumeStore";

export default function DataSourceNotice({
  tab,
}: {
  readonly tab: "overview" | "fixes" | "recruiter" | "gap";
}) {
  const fallbackInfo = useResumeStore((s) => s.fallbackInfo);
  const entries = fallbackInfo[tab] ?? [];

  if (entries.length === 0) {
    return (
      <div
        style={{
          marginTop: "18px",
          fontSize: "12px",
          color: "#16a34a",
          background: "#f0fdf4",
          border: "1px solid #bbf7d0",
          borderRadius: "10px",
          padding: "10px 12px",
        }}
      >
        Data source check: all visible data on this page is from API.
      </div>
    );
  }

  return (
    <div
      style={{
        marginTop: "18px",
        fontSize: "12px",
        color: "#d97706",
        background: "#fefce8",
        border: "1px solid #fde68a",
        borderRadius: "10px",
        padding: "10px 12px",
        lineHeight: 1.6,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: "4px" }}>
        Debug: API data missing, using mock fallback
      </div>
      {entries.map((entry) => (
        <div key={entry}>- {entry}</div>
      ))}
    </div>
  );
}
