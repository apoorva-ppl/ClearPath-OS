import { useEffect, useMemo, useRef, useState } from "react";
import Panel from "@/components/clearpath/Panel";
import AnimatedNumber from "@/components/clearpath/AnimatedNumber";
import Gauge from "@/components/clearpath/Gauge";
import Badge, { severityVariant } from "@/components/clearpath/Badge";
import Skeleton from "@/components/clearpath/Skeleton";
import { getJSON, reverseGeocode } from "@/lib/api";

// Inject page-scoped crimson overrides while Debrief is mounted
function useDebriefColorMode() {
  useEffect(() => {
    const style = document.createElement("style");
    style.id = "debrief-color-override";
    style.textContent = `
      /* Shift active nav tab underline from orange → crimson */
      [data-page="debrief"] .nav-tab.active,
      [data-page="debrief"] .nav-tab[aria-current="page"],
      nav a[href*="debrief"].active,
      nav a[href*="debrief"][aria-current="page"],
      .nav-tab:has(+ *)[href*="debrief"],
      /* common nav active indicator patterns */
      .tab-active-indicator { border-color: #dc2626 !important; color: #dc2626 !important; }

      /* Crimson glow on the debrief page body */
      [data-testid="debrief-page"] {
        background: radial-gradient(ellipse 90% 40% at 50% 0%, rgba(185,28,28,0.07) 0%, transparent 70%);
      }

      /* Scatter canvas red dots pop harder */
      [data-testid="scatter-canvas"] { filter: saturate(1.15); }
    `;
    document.head.appendChild(style);

    // Also mark the nearest nav tab as debrief-active via attribute
    // so parent layout CSS can respond if it watches data attributes
    document.documentElement.setAttribute("data-active-tab", "debrief");

    return () => {
      document.getElementById("debrief-color-override")?.remove();
      document.documentElement.removeAttribute("data-active-tab");
    };
  }, []);
}
function ErrorHistogram({ incidents, selectedId }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const c = canvasRef.current;
    if (!c || !incidents.length) return;
    const dpr = window.devicePixelRatio || 1;
    const W = c.clientWidth || 400;
    const H = 140;
    c.width = W * dpr;
    c.height = H * dpr;
    c.style.height = `${H}px`;
    const ctx = c.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    // Build 20-bucket histogram 0–400min
    const BUCKETS = 20;
    const MAX_E = 400;
    const bins = Array(BUCKETS).fill(0);
    incidents.forEach((d) => {
      const e = Math.min(Math.abs(d.absolute_error || 0), MAX_E - 1);
      bins[Math.floor((e / MAX_E) * BUCKETS)]++;
    });
    const peak = Math.max(...bins);

    const PAD_L = 28,
      PAD_B = 24,
      PAD_T = 8,
      PAD_R = 8;
    const chartW = W - PAD_L - PAD_R;
    const chartH = H - PAD_B - PAD_T;
    const bw = chartW / BUCKETS;

    // Threshold lines
    const t20 = PAD_L + (20 / MAX_E) * chartW;
    const t60 = PAD_L + (60 / MAX_E) * chartW;

    ctx.strokeStyle = "rgba(16,185,129,0.25)";
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(t20, PAD_T);
    ctx.lineTo(t20, H - PAD_B);
    ctx.stroke();
    ctx.strokeStyle = "rgba(245,158,11,0.25)";
    ctx.beginPath();
    ctx.moveTo(t60, PAD_T);
    ctx.lineTo(t60, H - PAD_B);
    ctx.stroke();
    ctx.setLineDash([]);

    // Bars
    bins.forEach((count, i) => {
      const midErr = ((i + 0.5) / BUCKETS) * MAX_E;
      const col = midErr < 20 ? "#10b981" : midErr < 60 ? "#f59e0b" : "#ef4444";
      const barH = peak > 0 ? (count / peak) * chartH : 0;
      const bx = PAD_L + i * bw;
      const by = PAD_T + chartH - barH;

      ctx.fillStyle = col;
      ctx.globalAlpha = 0.75;
      ctx.fillRect(bx + 1, by, bw - 2, barH);
      ctx.globalAlpha = 1;

      // Highlight selected incident's bucket
      if (selectedId) {
        const sel = incidents.find((d) => d.id === selectedId);
        if (sel) {
          const selBucket = Math.floor(
            (Math.min(Math.abs(sel.absolute_error || 0), MAX_E - 1) / MAX_E) *
              BUCKETS,
          );
          if (selBucket === i) {
            ctx.strokeStyle = "#fff";
            ctx.lineWidth = 1.5;
            ctx.strokeRect(bx + 1, by, bw - 2, barH);
          }
        }
      }
    });

    // X axis
    ctx.fillStyle = "rgba(148,163,184,0.5)";
    ctx.font = "9px 'Share Tech Mono'";
    [0, 100, 200, 300, 400].forEach((v) => {
      const px = PAD_L + (v / MAX_E) * chartW;
      ctx.fillText(String(v), px - 6, H - 6);
    });

    // Y axis label
    ctx.fillStyle = "rgba(148,163,184,0.4)";
    ctx.font = "9px 'Share Tech Mono'";
    ctx.fillText(String(peak), 0, PAD_T + 8);
    ctx.fillText("0", 2, H - PAD_B + 2);
  }, [incidents, selectedId]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: "100%", height: 140, display: "block" }}
    />
  );
}

export default function Debrief() {
  const [data, setData] = useState(null);
  const [locationNames, setLocationNames] = useState({});
  const [phase, setPhase] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [anomalyProgress, setAnomalyProgress] = useState(0);
  const [retrainFlag, setRetrainFlag] = useState(false);
  const canvasRef = useRef(null);
  const tooltipRef = useRef(null);

  // Apply crimson color-temperature while on this page
  useDebriefColorMode();

  useEffect(() => {
    getJSON("/after-action")
      .then(setData)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const t1 = setTimeout(() => setPhase(1), 700);
    const t2 = setTimeout(() => setPhase(2), 1900);
    const t3 = setTimeout(() => setPhase(3), 3100);
    return () => [t1, t2, t3].forEach(clearTimeout);
  }, []);

  useEffect(() => {
    if (!data) return;
    const id = setInterval(() => {
      setAnomalyProgress((p) => {
        const next = p + 4;
        if (next >= 100) {
          clearInterval(id);
          setTimeout(() => setRetrainFlag(true), 400);
          return 100;
        }
        return next;
      });
    }, 80);
    return () => clearInterval(id);
  }, [data]);

  const summary = data?.summary || {};
  const incidents = useMemo(() => data?.incidents || [], [data?.incidents]);

  useEffect(() => {
    if (!incidents.length) return;
    incidents.slice(0, 200).forEach((inc, i) => {
      if (!inc.lat || !inc.lng) return;
      setTimeout(() => {
        reverseGeocode(inc.lat, inc.lng).then((name) => {
          setLocationNames((prev) => ({ ...prev, [inc.id]: name }));
        });
      }, i * 200);
    });
  }, [incidents]);

  const sorted = useMemo(
    () =>
      [...incidents]
        .sort((a, b) => (b.absolute_error || 0) - (a.absolute_error || 0))
        .slice(0, 200),
    [incidents],
  );

  // ===== Scatter canvas =====
  useEffect(() => {
    const c = canvasRef.current;
    if (!c || !incidents.length) return;
    const dpr = window.devicePixelRatio || 1;
    const W = c.clientWidth || 480;
    const H = 360;
    c.width = W * dpr;
    c.height = H * dpr;
    c.style.height = `${H}px`;
    const ctx = c.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    const PAD = 36;
    const MAX = 500;
    const x = (v) => PAD + (v / MAX) * (W - PAD - 12);
    const y = (v) => H - PAD - (v / MAX) * (H - PAD - 12);

    // grid
    ctx.strokeStyle = "rgba(148,163,184,0.08)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const v = (i / 5) * MAX;
      ctx.beginPath();
      ctx.moveTo(PAD, y(v));
      ctx.lineTo(W - 12, y(v));
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x(v), PAD);
      ctx.lineTo(x(v), H - PAD);
      ctx.stroke();
      ctx.fillStyle = "rgba(148,163,184,0.5)";
      ctx.font = "10px 'Share Tech Mono'";
      ctx.fillText(String(Math.round(v)), x(v) - 8, H - PAD + 14);
      ctx.fillText(String(Math.round(v)), 6, y(v) + 4);
    }

    ctx.fillStyle = "var(--text-dim)";
    ctx.font = "10px 'Rajdhani'";
    ctx.fillText("PREDICTED →", W - 80, H - 6);
    ctx.save();
    ctx.translate(12, 30);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("← ACTUAL", -40, 0);
    ctx.restore();

    // diagonal — crimson tint instead of cyan
    ctx.strokeStyle = "rgba(220,38,38,0.35)";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x(0), y(0));
    ctx.lineTo(x(MAX), y(MAX));
    ctx.stroke();
    ctx.setLineDash([]);

    // dots
    incidents.forEach((d) => {
      const p = Math.min(d.predicted_minutes || 0, MAX);
      const a = Math.min(d.actual_minutes || 0, MAX);
      const e = Math.abs(d.absolute_error || 0);
      const col = e < 20 ? "#10b981" : e < 60 ? "#f59e0b" : "#ef4444";
      const sel = d.id === selectedId;
      ctx.beginPath();
      ctx.arc(x(p), y(a), sel ? 6 : 3, 0, Math.PI * 2);
      ctx.fillStyle = col;
      ctx.globalAlpha = sel ? 1 : 0.7;
      ctx.fill();
      if (sel) {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    });

    const onMove = (ev) => {
      const rect = c.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      let hit = null;
      let best = 14;
      for (const d of incidents) {
        const dx = x(Math.min(d.predicted_minutes || 0, MAX)) - mx;
        const dy = y(Math.min(d.actual_minutes || 0, MAX)) - my;
        const dist = Math.hypot(dx, dy);
        if (dist < best) {
          best = dist;
          hit = d;
        }
      }
      const tt = tooltipRef.current;
      if (tt && hit) {
        tt.style.display = "block";
        tt.style.left = `${ev.clientX - rect.left + 14}px`;
        tt.style.top = `${ev.clientY - rect.top + 14}px`;
        tt.innerHTML = `<b style="color:var(--orange)">${hit.id}</b><br/>${hit.event_cause}<br/>actual <b>${hit.actual_minutes}m</b> · pred <b>${hit.predicted_minutes}m</b><br/>err <b style="color:var(--red)">${Math.abs(hit.absolute_error || 0).toFixed(1)}m</b>`;
      } else if (tt) tt.style.display = "none";
    };
    const onClick = (ev) => {
      const rect = c.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      let hit = null;
      let best = 14;
      for (const d of incidents) {
        const dx = x(Math.min(d.predicted_minutes || 0, MAX)) - mx;
        const dy = y(Math.min(d.actual_minutes || 0, MAX)) - my;
        const dist = Math.hypot(dx, dy);
        if (dist < best) {
          best = dist;
          hit = d;
        }
      }
      if (hit) setSelectedId(hit.id);
    };
    c.addEventListener("mousemove", onMove);
    c.addEventListener("click", onClick);
    c.addEventListener("mouseleave", () => {
      if (tooltipRef.current) tooltipRef.current.style.display = "none";
    });
    return () => {
      c.removeEventListener("mousemove", onMove);
      c.removeEventListener("click", onClick);
    };
  }, [incidents, selectedId]);

  const driftPct = summary.mean_actual_minutes
    ? (summary.median_absolute_error / summary.mean_actual_minutes) * 100
    : 0;

  return (
    <div
      style={{
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        minHeight: "calc(100vh - 49px)",
      }}
      data-testid="debrief-page"
      data-page="debrief"
    >
      {/* ── OPENER ── */}
      <div
        className="panel"
        style={{
          padding: "30px 32px",
          textAlign: "center",
          position: "relative",
          overflow: "hidden",
          // Subtle crimson top-border to distinguish from Intelligence orange
          borderTop: "2px solid rgba(220,38,38,0.6)",
        }}
        data-testid="opener"
      >
        {/* ── POST-MORTEM STATE BADGE ── */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 7,
            marginBottom: 18,
            padding: "4px 10px",
            border: "1px solid rgba(185,28,28,0.45)",
            borderRadius: 2,
            background: "rgba(185,28,28,0.08)",
            opacity: phase >= 1 ? 1 : 0,
            transition: "opacity 0.5s ease",
          }}
        >
          {/* Static dot — no pulse, this is offline data */}
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "#7f1d1d",
              display: "inline-block",
              flexShrink: 0,
            }}
          />
          <span
            className="mono"
            style={{
              fontSize: 10,
              letterSpacing: "0.2em",
              color: "#b91c1c",
            }}
          >
            OFFLINE BATCH EVALUATION · POST-MORTEM
          </span>
        </div>

        <div
          className="display"
          style={{
            fontSize: 36,
            color: "var(--red)",
            letterSpacing: "0.14em",
            textShadow: "0 0 24px rgba(239,68,68,0.6)",
            opacity: phase >= 1 ? 1 : 0,
            transform: phase >= 1 ? "translateY(0)" : "translateY(20px)",
            transition: "all 0.7s cubic-bezier(0.16,1,0.3,1)",
          }}
        >
          THE MODEL MADE MISTAKES.
        </div>
        <div
          className="display"
          style={{
            fontSize: 22,
            color: "var(--text-dim)",
            letterSpacing: "0.18em",
            marginTop: 12,
            opacity: phase >= 2 ? 1 : 0,
            transform: phase >= 2 ? "translateY(0)" : "translateY(20px)",
            transition: "all 0.7s cubic-bezier(0.16,1,0.3,1) 0.2s",
          }}
        >
          HERE IS EVERY ONE OF THEM.
        </div>
      </div>

      <div
        style={{ display: "grid", gridTemplateColumns: "1.05fr 1fr", gap: 14 }}
      >
        {/* LEFT */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Panel
            title="PREDICTED VS ACTUAL · MINUTES"
            right={
              <span
                className="mono"
                style={{ fontSize: 10, color: "var(--text-mute)" }}
              >
                {incidents.length} POINTS
              </span>
            }
            testId="scatter-panel"
          >
            <div style={{ position: "relative" }}>
              <canvas
                ref={canvasRef}
                style={{ width: "100%", height: 360 }}
                data-testid="scatter-canvas"
              />
              <div
                ref={tooltipRef}
                className="mono"
                style={{
                  position: "absolute",
                  display: "none",
                  background: "rgba(10,14,22,0.95)",
                  border: "1px solid var(--border-strong)",
                  padding: 8,
                  borderRadius: 3,
                  fontSize: 11,
                  color: "var(--text)",
                  pointerEvents: "none",
                  boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
                  zIndex: 10,
                }}
              />
              <div
                style={{
                  display: "flex",
                  gap: 16,
                  marginTop: 8,
                  justifyContent: "center",
                  fontSize: 10,
                }}
              >
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 5,
                      background: "var(--green)",
                    }}
                  />
                  &lt; 20m err
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 5,
                      background: "var(--amber)",
                    }}
                  />
                  20–60m
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 5,
                      background: "var(--red)",
                    }}
                  />
                  &gt; 60m
                </span>
              </div>
            </div>
          </Panel>

          <Panel title="DRIFT GAUGE" testId="drift-gauge-panel">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Gauge
                value={driftPct}
                size={260}
                label="MEDIAN / MEAN"
                testId="drift-gauge"
              />
            </div>
            <div
              className="mono"
              style={{
                fontSize: 11,
                color: "var(--text-mute)",
                textAlign: "center",
                marginTop: 8,
              }}
            >
              (median_absolute_error / mean_actual_minutes) × 100
            </div>

            {/* ── MODEL HEALTH VITALS ── */}
            <div
              style={{
                marginTop: 24,
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              {[
                {
                  label: "PREDICTION BIAS",
                  value: driftPct,
                  max: 100,
                  color:
                    driftPct > 40
                      ? "#ef4444"
                      : driftPct > 20
                        ? "#f59e0b"
                        : "#10b981",
                },
                {
                  label: "LONG-TAIL EXPOSURE",
                  value: Math.min((summary.mean_actual_minutes || 0) / 3, 100),
                  max: 100,
                  color: "#ef4444",
                },
                {
                  label: "CALIBRATION SCORE",
                  value: Math.max(0, 100 - driftPct * 1.4),
                  max: 100,
                  color: "#06b6d4",
                },
              ].map(({ label, value, color }) => (
                <div key={label}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: 4,
                    }}
                  >
                    <span
                      className="mono"
                      style={{
                        fontSize: 10,
                        color: "var(--text-mute)",
                        letterSpacing: "0.14em",
                      }}
                    >
                      {label}
                    </span>
                    <span className="mono" style={{ fontSize: 10, color }}>
                      {value.toFixed(1)}%
                    </span>
                  </div>
                  <div
                    style={{
                      height: 3,
                      background: "rgba(255,255,255,0.06)",
                      borderRadius: 2,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(value, 100)}%`,
                        background: color,
                        boxShadow: `0 0 8px ${color}`,
                        borderRadius: 2,
                        transition: "width 1.2s cubic-bezier(0.16,1,0.3,1)",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        {/* RIGHT */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div
            style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}
          >
            <div className="stat-card" data-testid="stat-total">
              <div className="label">TOTAL INCIDENTS</div>
              <div className="value">
                <AnimatedNumber value={summary.total_incidents || 0} />
              </div>
            </div>
            <div className="stat-card" data-testid="stat-med-ae">
              <div className="label">MEDIAN ABS. ERROR</div>
              <div className="value" style={{ color: "var(--orange)" }}>
                <AnimatedNumber
                  value={summary.median_absolute_error || 0}
                  decimals={1}
                  suffix="m"
                />
              </div>
            </div>
            <div className="stat-card">
              <div className="label">MEAN ACTUAL</div>
              <div className="value">
                <AnimatedNumber
                  value={summary.mean_actual_minutes || 0}
                  decimals={1}
                  suffix="m"
                />
              </div>
            </div>
            <div className="stat-card">
              <div className="label">MEAN PREDICTED</div>
              <div className="value" style={{ color: "var(--cyan)" }}>
                <AnimatedNumber
                  value={summary.mean_predicted_minutes || 0}
                  decimals={1}
                  suffix="m"
                />
              </div>
            </div>
          </div>

          {summary.drift_note && (
            <div
              className="fade-in"
              style={{
                border: "1px solid var(--amber)",
                background: "rgba(245,158,11,0.08)",
                padding: 14,
                borderRadius: 4,
              }}
              data-testid="drift-note"
            >
              <div
                className="display"
                style={{
                  fontSize: 11,
                  color: "var(--amber)",
                  marginBottom: 6,
                  letterSpacing: "0.18em",
                }}
              >
                ⚠ DRIFT NOTE
              </div>
              <div
                className="mono"
                style={{ fontSize: 12, color: "var(--text)", lineHeight: 1.5 }}
              >
                {summary.drift_note}
              </div>
            </div>
          )}

          <Panel title="WHAT THIS MEANS" testId="meaning-panel">
            <div
              style={{
                fontSize: 13,
                color: "var(--text-dim)",
                lineHeight: 1.6,
              }}
            >
              The model&apos;s median absolute error indicates a systematic
              miscalibration on long-tail incidents. Closure-window predictions
              underestimate when the corridor has historical recurring
              blockages. We keep these mistakes visible — not buried — to drive
              the next retraining cycle.
            </div>
          </Panel>

          <Panel title="ANOMALY DETECTION" testId="anomaly-panel">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: 8,
              }}
            >
              <span
                className="display"
                style={{
                  fontSize: 12,
                  color: "var(--red)",
                  textShadow: "0 0 8px var(--red)",
                }}
              >
                23 ANOMALIES DETECTED
              </span>
              <span
                className="mono"
                style={{ fontSize: 11, color: "var(--text-mute)" }}
              >
                {anomalyProgress}%
              </span>
            </div>
            <div className="abar" style={{ height: 8 }}>
              <div
                className="abar-fill red"
                style={{ width: `${anomalyProgress}%` }}
              />
            </div>
            {retrainFlag && (
              <div
                className="fade-in display"
                style={{
                  marginTop: 12,
                  padding: 10,
                  background: "rgba(239,68,68,0.12)",
                  border: "1px solid var(--red)",
                  borderRadius: 3,
                  color: "var(--red)",
                  textAlign: "center",
                  fontSize: 11,
                  letterSpacing: "0.16em",
                }}
              >
                ▶ FLAGGED FOR RETRAINING EPOCH
              </div>
            )}
          </Panel>

          <Panel
            title={`TOP 200 BY ERROR · CLICK TO LINK`}
            testId="top200-panel"
          >
            <div style={{ maxHeight: 320, overflow: "auto" }}>
              {sorted.length === 0 &&
                Array.from({ length: 8 }).map((_, i) => (
                  <Skeleton key={i} height={18} style={{ marginBottom: 6 }} />
                ))}
              {sorted.map((r) => {
                const sev = severityVariant(
                  r.severity ||
                    (r.absolute_error > 60
                      ? "HIGH"
                      : r.absolute_error > 20
                        ? "MEDIUM"
                        : "LOW"),
                );
                const bg =
                  sev === "high"
                    ? "rgba(239,68,68,0.08)"
                    : sev === "medium"
                      ? "rgba(245,158,11,0.06)"
                      : "transparent";
                const sel = selectedId === r.id;
                return (
                  <div
                    key={r.id}
                    onClick={() => setSelectedId(r.id)}
                    data-testid={`row-${r.id}`}
                    style={{
                      padding: "6px 8px",
                      background: sel ? "rgba(220,38,38,0.15)" : bg,
                      borderLeft: sel
                        ? "3px solid #dc2626"
                        : "3px solid transparent",
                      display: "grid",
                      gridTemplateColumns: "70px 1fr auto auto auto",
                      gap: 8,
                      alignItems: "center",
                      cursor: "pointer",
                      transition: "background 0.15s",
                    }}
                  >
                    <span
                      className="mono"
                      style={{ fontSize: 10, color: "var(--text-dim)" }}
                    >
                      {r.id}
                    </span>
                    <span
                      className="mono"
                      style={{ fontSize: 10, color: "var(--text)" }}
                    >
                      {locationNames[r.id]
                        ? `${locationNames[r.id]} · ${r.event_cause}`
                        : r.event_cause}
                    </span>
                    <span
                      className="mono"
                      style={{ fontSize: 10, color: "var(--cyan)" }}
                    >
                      p={r.predicted_minutes}m
                    </span>
                    <span
                      className="mono"
                      style={{ fontSize: 10, color: "var(--text-dim)" }}
                    >
                      a={r.actual_minutes}m
                    </span>
                    <span
                      className="mono"
                      style={{ fontSize: 10, color: "var(--red)" }}
                    >
                      ±{(r.absolute_error || 0).toFixed(1)}
                    </span>
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
