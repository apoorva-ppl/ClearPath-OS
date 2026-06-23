import Spinner from "./Spinner";

const ICON = {
    init: "⊙",
    triage: "⚕",
    spatial: "◈",
    logistics: "⛬",
    supervisor: "⚙",
    directive: "✉",
    complete: "✔",
    error: "✕",
};

export default function AgentStepRow({ step, status, message, accent = "orange" }) {
    const live = status === "running" || status === "pending";
    const done = status === "done" || status === "complete";
    const failed = status === "error";

    return (
        <div
            className="fade-in"
            data-testid={`agent-row-${step}`}
            style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 12,
                padding: "10px 12px",
                borderLeft: `2px solid ${
                    failed ? "var(--red)" : done ? "var(--green)" : live ? "var(--orange)" : "var(--border)"
                }`,
                background: live ? "rgba(249,115,22,0.05)" : "transparent",
                borderRadius: "0 4px 4px 0",
                transition: "background 0.3s",
            }}
        >
            <div
                style={{
                    width: 28,
                    height: 28,
                    flexShrink: 0,
                    borderRadius: 4,
                    background: failed
                        ? "rgba(239,68,68,0.15)"
                        : done
                          ? "rgba(16,185,129,0.15)"
                          : live
                            ? "rgba(249,115,22,0.15)"
                            : "rgba(148,163,184,0.06)",
                    color: failed
                        ? "var(--red)"
                        : done
                          ? "var(--green)"
                          : live
                            ? "var(--orange)"
                            : "var(--text-mute)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: "var(--font-mono)",
                    fontSize: 14,
                    boxShadow: live ? `0 0 12px rgba(249,115,22,0.4)` : "none",
                }}
            >
                {live ? <Spinner /> : ICON[step] || "·"}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
                <div
                    className="display"
                    style={{
                        fontSize: 11,
                        color: done
                            ? "var(--green)"
                            : failed
                              ? "var(--red)"
                              : live
                                ? "var(--orange)"
                                : "var(--text-dim)",
                    }}
                >
                    {step}
                </div>
                <div
                    className="mono"
                    style={{
                        fontSize: 11,
                        color: "var(--text-dim)",
                        marginTop: 3,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                    }}
                >
                    {message || (live ? "processing…" : "—")}
                </div>
            </div>
        </div>
    );
}
