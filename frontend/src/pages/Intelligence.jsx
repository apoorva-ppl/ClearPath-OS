import { useEffect, useMemo, useRef, useState } from "react";
import Panel from "@/components/clearpath/Panel";
import AnimatedBar from "@/components/clearpath/AnimatedBar";
import AnimatedNumber from "@/components/clearpath/AnimatedNumber";
import Skeleton from "@/components/clearpath/Skeleton";
import Badge, { severityVariant } from "@/components/clearpath/Badge";
import LiveDot from "@/components/clearpath/LiveDot";
import { getJSON } from "@/lib/api";
import SplineScene from "@/components/clearpath/SplineScene";

export default function Intelligence() {
  const [metrics, setMetrics] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [scrollIdx, setScrollIdx] = useState(0);
  const feedRef = useRef(null);

  useEffect(() => {
    getJSON("/metrics")
      .then(setMetrics)
      .catch(() => {});
    getJSON("/incidents")
      .then(setIncidents)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!incidents.length) return;
    const id = setInterval(
      () => setScrollIdx((i) => (i + 1) % incidents.length),
      1800,
    );
    return () => clearInterval(id);
  }, [incidents]);

  const closure = metrics?.closure || {};
  const duration = metrics?.duration || {};
  const cm = closure.confusion_matrix || [
    [0, 0],
    [0, 0],
  ];

  const causeStats = useMemo(() => {
    const m = {};
    incidents.forEach((i) => {
      const k = i.event_cause || "unknown";
      m[k] = (m[k] || 0) + 1;
    });
    const list = Object.entries(m).map(([k, v]) => ({
      k,
      v,
      pct: (v / incidents.length) * 100,
    }));
    return list.sort((a, b) => b.v - a.v).slice(0, 8);
  }, [incidents]);

  const hourMap = useMemo(() => {
    const arr = Array(24).fill(0);
    incidents.forEach((i) => {
      const h = Number(i.hour);
      if (!isNaN(h)) arr[h] += 1;
    });
    const max = Math.max(1, ...arr);
    return { arr, max };
  }, [incidents]);

  const corridorStats = useMemo(() => {
    const m = {};
    incidents.forEach((i) => {
      const k = i.corridor || "unknown";
      m[k] = (m[k] || 0) + 1;
    });
    const list = Object.entries(m).map(([k, v]) => ({ k, v }));
    return list.sort((a, b) => b.v - a.v).slice(0, 10);
  }, [incidents]);

  const visibleFeed = incidents.length
    ? Array.from({ length: 18 }).map(
        (_, i) => incidents[(scrollIdx + i) % incidents.length],
      )
    : [];

  return (
    <div
      style={{
        padding: 16,
        display: "grid",
        gridTemplateColumns: "1.1fr 1fr 1fr",
        gap: 16,
        minHeight: "calc(100vh - 49px)",
      }}
      data-testid="intelligence-page"
    >
      {/* LEFT */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Panel
          title="CLOSURE MODEL"
          right={<Badge variant="info">CLASSIFIER</Badge>}
          testId="model-panel"
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {metrics ? (
              <>
                <AnimatedBar
                  value={(closure.roc_auc || 0) * 100}
                  max={100}
                  color="cyan"
                  label="ROC-AUC"
                  valueLabel={(closure.roc_auc || 0).toFixed(3)}
                />
                <AnimatedBar
                  value={(closure.pr_auc || 0) * 100}
                  max={100}
                  color="orange"
                  label="PR-AUC"
                  valueLabel={(closure.pr_auc || 0).toFixed(3)}
                  delay={120}
                />
                <AnimatedBar
                  value={(closure.closure_recall || 0) * 100}
                  max={100}
                  color="green"
                  label="RECALL (CLOSURE)"
                  valueLabel={(closure.closure_recall || 0).toFixed(3)}
                  delay={240}
                />
                <AnimatedBar
                  value={(closure.closure_precision || 0) * 100}
                  max={100}
                  color="amber"
                  label="PRECISION (CLOSURE)"
                  valueLabel={(closure.closure_precision || 0).toFixed(3)}
                  delay={360}
                />
              </>
            ) : (
              Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} height={18} />
              ))
            )}
          </div>

          <div
            style={{
              marginTop: 16,
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 8,
            }}
          >
            {[
              { l: "TN", v: cm?.[0]?.[0], good: true },
              { l: "FP", v: cm?.[0]?.[1], good: false },
              { l: "FN", v: cm?.[1]?.[0], good: false },
              { l: "TP", v: cm?.[1]?.[1], good: true },
            ].map((c) => (
              <div
                key={c.l}
                style={{
                  padding: 10,
                  background: c.good
                    ? "rgba(16,185,129,0.08)"
                    : "rgba(239,68,68,0.08)",
                  border: `1px solid ${c.good ? "var(--green)" : "var(--red)"}`,
                  borderRadius: 3,
                  textAlign: "center",
                }}
              >
                <div
                  className="display"
                  style={{
                    fontSize: 9,
                    color: c.good ? "var(--green)" : "var(--red)",
                    letterSpacing: "0.16em",
                  }}
                >
                  {c.l}
                </div>
                <div
                  className="mono"
                  style={{ fontSize: 20, color: "var(--text)" }}
                >
                  <AnimatedNumber value={c.v || 0} />
                </div>
              </div>
            ))}
          </div>

          <div
            className="mono fade-in"
            style={{
              fontSize: 10,
              color: "var(--text-mute)",
              marginTop: 10,
              lineHeight: 1.5,
            }}
          >
            ⓘ Closure rate ≈ 7.4% (class imbalance). Threshold tuned for recall.
            {closure.decision_threshold != null && (
              <>
                {" "}
                · θ ={" "}
                <b style={{ color: "var(--orange)" }}>
                  {closure.decision_threshold.toFixed(3)}
                </b>
              </>
            )}
          </div>
        </Panel>

        <Panel title="DURATION REGRESSOR" testId="duration-panel">
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              gap: 16,
              marginBottom: 10,
            }}
          >
            <div>
              <div
                className="display"
                style={{ fontSize: 10, color: "var(--text-dim)" }}
              >
                MEDIAN-AE
              </div>
              <div
                className="mono"
                style={{
                  fontSize: 40,
                  color: "var(--orange)",
                  textShadow: "0 0 12px rgba(249,115,22,0.4)",
                }}
              >
                <AnimatedNumber
                  value={duration.median_ae_minutes || 0}
                  decimals={1}
                  suffix=" min"
                />
              </div>
            </div>
            <div>
              <div
                className="display"
                style={{ fontSize: 10, color: "var(--text-dim)" }}
              >
                MAE
              </div>
              <div
                className="mono"
                style={{ fontSize: 22, color: "var(--cyan)" }}
              >
                <AnimatedNumber
                  value={duration.mae_minutes || 0}
                  decimals={1}
                  suffix="m"
                />
              </div>
            </div>
          </div>
          <div
            className="mono"
            style={{ fontSize: 10, color: "var(--text-mute)" }}
          >
            Train:{" "}
            <b style={{ color: "var(--text-dim)" }}>
              {duration.n_train || "—"}
            </b>{" "}
            · Val:{" "}
            <b style={{ color: "var(--text-dim)" }}>{duration.n_val || "—"}</b>
          </div>
        </Panel>
      </div>

      {/* CENTER — spline + feed */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div
          style={{
            height: 200,
            borderRadius: 4,
            overflow: "hidden",
            border: "1px solid rgba(6,182,212,0.12)",
            position: "relative",
          }}
        >
          <SplineScene />
          <div
            style={{
              position: "absolute",
              inset: 0,
              background:
                "radial-gradient(ellipse at center, transparent 50%, rgba(8,12,20,0.85) 100%)",
              pointerEvents: "none",
            }}
          />
        </div>
        <Panel
          title="LIVE INCIDENT FEED"
          right={
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                className="mono"
                style={{
                  fontSize: 9,
                  color: "var(--green)",
                  letterSpacing: "0.16em",
                }}
              >
                [ LIVE TELEMETRY ]
              </span>
              <LiveDot variant="green" />
            </div>
          }
          testId="live-feed-panel"
        >
          <div
            ref={feedRef}
            style={{ maxHeight: "calc(100vh - 380px)", overflow: "hidden" }}
          >
            {!incidents.length &&
              Array.from({ length: 12 }).map((_, i) => (
                <Skeleton key={i} height={22} style={{ marginBottom: 6 }} />
              ))}
            {visibleFeed.map((i, k) => (
              <div
                key={`${i.id}-${k}`}
                className="fade-in"
                style={{
                  padding: "8px 0",
                  borderBottom: "1px solid rgba(148,163,184,0.05)",
                  display: "grid",
                  gridTemplateColumns: "auto 1fr auto",
                  gap: 10,
                  alignItems: "center",
                }}
              >
                <span
                  className="mono"
                  style={{ fontSize: 10, color: "var(--text-mute)" }}
                >
                  {i.id}
                </span>
                <span>
                  <div
                    className="mono"
                    style={{ fontSize: 11, color: "var(--text)" }}
                  >
                    {i.event_cause} ·{" "}
                    <span style={{ color: "var(--text-dim)" }}>
                      {i.corridor}
                    </span>
                  </div>
                  <div
                    className="mono"
                    style={{ fontSize: 9, color: "var(--text-mute)" }}
                  >
                    h={i.hour} · {i.duration_display || "—"}
                  </div>
                </span>
                <Badge variant={severityVariant(i.severity)}>
                  {i.severity}
                </Badge>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* RIGHT — breakdowns */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Panel title="CAUSE BREAKDOWN" testId="cause-panel">
          {causeStats.length === 0 &&
            Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} height={20} style={{ marginBottom: 8 }} />
            ))}
          {causeStats.map((c, i) => (
            <div key={c.k} style={{ marginBottom: 10 }}>
              <AnimatedBar
                value={c.pct}
                max={Math.max(50, causeStats[0]?.pct || 50)}
                color={i === 0 ? "orange" : i === 1 ? "cyan" : "amber"}
                label={c.k}
                valueLabel={`${c.v} · ${c.pct.toFixed(1)}%`}
                delay={i * 60}
              />
            </div>
          ))}
        </Panel>

        <Panel title="HOURLY HEATMAP · 24H" testId="hour-panel">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(12,1fr)",
              gap: 4,
            }}
          >
            {hourMap.arr.map((v, h) => {
              const op = 0.1 + 0.9 * (v / hourMap.max);
              return (
                <div
                  key={h}
                  title={`${String(h).padStart(2, "0")}:00 · ${v} incidents`}
                  style={{
                    height: 26,
                    background: `rgba(249,115,22,${op})`,
                    border: "1px solid rgba(249,115,22,0.3)",
                    borderRadius: 2,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: "var(--font-mono)",
                    fontSize: 9,
                    color: op > 0.5 ? "#000" : "var(--text-dim)",
                    transition: "transform 0.15s",
                    cursor: "default",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.transform = "scale(1.15)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.transform = "scale(1)")
                  }
                  data-testid={`hour-${h}`}
                >
                  {String(h).padStart(2, "0")}
                </div>
              );
            })}
          </div>
        </Panel>

        <Panel title="CORRIDOR RISK · TOP 10" testId="corridor-panel">
          {corridorStats.length === 0 &&
            Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} height={18} style={{ marginBottom: 6 }} />
            ))}
          {corridorStats.map((c, i) => (
            <div key={c.k} style={{ marginBottom: 8 }}>
              <AnimatedBar
                value={c.v}
                max={Math.max(1, corridorStats[0]?.v || 1)}
                color={i < 3 ? "red" : i < 6 ? "amber" : "cyan"}
                label={c.k}
                valueLabel={String(c.v)}
                delay={i * 50}
              />
            </div>
          ))}
        </Panel>
      </div>
    </div>
  );
}
