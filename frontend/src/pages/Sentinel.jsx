import { useCallback, useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, CircleMarker } from "react-leaflet";
import Panel from "@/components/clearpath/Panel";
import Badge from "@/components/clearpath/Badge";
import LiveDot from "@/components/clearpath/LiveDot";
import AgentStepRow from "@/components/clearpath/AgentStepRow";
import VoicePulse from "@/components/clearpath/VoicePulse";
import ComplaintForm from "@/components/clearpath/ComplaintForm";
import AnimatedNumber from "@/components/clearpath/AnimatedNumber";
import { API } from "@/lib/api";
import { callPlanStream } from "@/lib/parsePlanStream";

const CENTER = [12.9716, 77.5946];

function jitter(v, d = 0.04) {
  return v + (Math.random() - 0.5) * d;
}
function distM(a, b) {
  const R = 6371000;
  const toRad = (x) => (x * Math.PI) / 180;
  const dLat = toRad(b[0] - a[0]);
  const dLng = toRad(b[1] - a[1]);
  const lat1 = toRad(a[0]);
  const lat2 = toRad(b[0]);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export default function Sentinel() {
  const [reports, setReports] = useState([]);
  const [swarm, setSwarm] = useState(null);
  const [steps, setSteps] = useState({});
  const [autonomous, setAutonomous] = useState(false);

  const onSubmitted = useCallback((complaint) => {
    const lat = jitter(CENTER[0], 0.06);
    const lng = jitter(CENTER[1], 0.06);
    setReports((r) =>
      [
        {
          id: complaint.id,
          ts: new Date(complaint.submitted_at),
          lat,
          lng,
          lang: complaint.language,
          category: complaint.category,
          text: complaint.text,
        },
        ...r,
      ].slice(0, 80),
    );
  }, []);

  const detectLang = (text) => (/[\u0C80-\u0CFF]/.test(text) ? "kn" : "en");

  const handleChange = (e) => {
    const text = e.target.value;
    setForm((f) => ({ ...f, text, language: detectLang(text) }));
  };

  const triggerSwarm = useCallback(async ({ lat, lng, count }) => {
    setSwarm({ lat, lng, count, ts: new Date() });
    setSteps({});
    try {
      await callPlanStream(
        API,
        {
          lat,
          lng,
          cause: "others",
          priority: "high",
          event_cause: "others",
          event_type: "others",
          corridor: "ORR North 1",
        },
        (evt) => {
          setSteps((s) => ({ ...s, [evt.step]: evt }));
          if (evt.step === "complete")
            setTimeout(() => setAutonomous(true), 400);
        },
      );
    } catch (e) {
      setSteps((s) => ({ ...s, error: { message: e.message } }));
    }
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      const now = Date.now();
      const recent = reports.filter(
        (r) => now - r.ts.getTime() < 5 * 60 * 1000,
      );
      for (let i = 0; i < recent.length; i++) {
        const near = recent.filter(
          (r) => distM([recent[i].lat, recent[i].lng], [r.lat, r.lng]) < 500,
        );
        if (near.length >= 3 && !swarm) {
          const cx = near.reduce((a, r) => a + r.lat, 0) / near.length;
          const cy = near.reduce((a, r) => a + r.lng, 0) / near.length;
          triggerSwarm({ lat: cx, lng: cy, count: near.length });
          return;
        }
      }
    }, 10000);
    return () => clearInterval(id);
  }, [reports, swarm, triggerSwarm]);

  const seedSwarmDemo = () => {
    const lat = jitter(CENTER[0], 0.02);
    const lng = jitter(CENTER[1], 0.02);
    const fresh = Array.from({ length: 3 }).map((_, i) => ({
      id: `R${Date.now()}_${i}`,
      ts: new Date(),
      lat: lat + (Math.random() - 0.5) * 0.001,
      lng: lng + (Math.random() - 0.5) * 0.001,
      lang: i === 0 ? "kn" : "en",
      category: "missed_closure",
      text:
        i === 0
          ? "ಸಿಗ್ನಲ್ ಬಳಿ ಮರ ಬಿದ್ದಿದೆ — ಮಾದರಿ ಇದನ್ನು ತಪ್ಪಿಸಿಕೊಂಡಿತು"
          : "Fallen tree near signal — the model missed this",
    }));
    setReports((r) => [...fresh, ...r].slice(0, 80));
  };

  const last24h = reports.length;
  const knCount = reports.filter((r) => r.lang === "kn").length;
  const enCount = reports.length - knCount;

  return (
    <div
      style={{
        minHeight: "calc(100vh - 49px)",
        padding: 18,
        display: "flex",
        flexDirection: "column",
        gap: 14,
        alignItems: "center",
      }}
      data-testid="complaint-portal-page"
      className="page-enter"
    >
      <ComplaintHeader
        total={last24h}
        en={enCount}
        kn={knCount}
        onSeed={seedSwarmDemo}
      />

      <div
        style={{ display: "grid", gridTemplateColumns: "1.55fr 1fr", gap: 14 }}
      >
        <ComplaintForm onSubmitted={onSubmitted} />

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Panel
            title="LIVE COMPLAINT GRID"
            right={<LiveDot variant="amber" />}
            testId="grid-panel"
            style={{ height: 320 }}
          >
            <div style={{ height: 260, position: "relative" }}>
              <MapContainer
                center={CENTER}
                zoom={11}
                style={{ width: "100%", height: "100%", borderRadius: 4 }}
                preferCanvas
                attributionControl={false}
              >
                <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png" />
                {reports.map((r) => (
                  <CircleMarker
                    key={r.id}
                    center={[r.lat, r.lng]}
                    radius={6}
                    pathOptions={{
                      color: r.lang === "kn" ? "#f97316" : "#06b6d4",
                      fillColor: r.lang === "kn" ? "#f97316" : "#06b6d4",
                      fillOpacity: 0.65,
                      weight: 2,
                    }}
                  />
                ))}
                {swarm && (
                  <CircleMarker
                    center={[swarm.lat, swarm.lng]}
                    radius={14}
                    pathOptions={{
                      color: "#ef4444",
                      fillColor: "#ef4444",
                      fillOpacity: 0.3,
                      weight: 3,
                    }}
                  />
                )}
              </MapContainer>
              <div
                style={{
                  position: "absolute",
                  bottom: 8,
                  left: 8,
                  display: "flex",
                  gap: 12,
                  padding: "5px 10px",
                  background: "rgba(10,14,22,0.85)",
                  borderRadius: 3,
                  border: "1px solid var(--border)",
                }}
              >
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 5,
                      background: "#06b6d4",
                    }}
                  />
                  <span
                    className="mono"
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      color: "rgba(255,255,255,0.85)",
                    }}
                  >
                    EN
                  </span>
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 5,
                      background: "#f97316",
                    }}
                  />
                  <span
                    className="mono"
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      color: "rgba(255,255,255,0.85)",
                    }}
                  >
                    ಕನ್ನಡ
                  </span>
                </span>
                {swarm && (
                  <span
                    style={{ display: "flex", alignItems: "center", gap: 6 }}
                  >
                    <span
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: 5,
                        background: "#ef4444",
                      }}
                    />
                    <span
                      className="mono"
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: "rgba(255,255,255,0.85)",
                      }}
                    >
                      SWARM
                    </span>
                  </span>
                )}
              </div>
            </div>
          </Panel>

          {swarm ? (
            <Panel
              title="SWARM"
              right={<Badge variant="high">THRESHOLD CROSSED</Badge>}
              testId="swarm-panel"
            >
              <div
                className="mono fade-in"
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "var(--orange)",
                  marginBottom: 8,
                }}
              >
                ⚠ {swarm.count} REPORTS · {swarm.lat.toFixed(4)},
                {swarm.lng.toFixed(4)}
              </div>
              {[
                "triage",
                "spatial",
                "logistics",
                "supervisor",
                "directive",
                "complete",
              ].map((s) => (
                <AgentStepRow
                  key={s}
                  step={s}
                  status={steps[s] ? "done" : "pending"}
                  message={steps[s]?.message || "queued"}
                />
              ))}
              {autonomous && (
                <div
                  className="slide-up display"
                  style={{
                    marginTop: 10,
                    padding: 10,
                    background: "rgba(239,68,68,0.12)",
                    border: "1px solid var(--red)",
                    borderRadius: 3,
                    color: "var(--red)",
                    textAlign: "center",
                    fontSize: 11,
                    fontWeight: 700,
                    textShadow: "0 0 8px var(--red)",
                  }}
                >
                  AUTONOMOUS DISPATCH TRIGGERED — NO HUMAN IN LOOP
                </div>
              )}
            </Panel>
          ) : (
            <Panel
              title="SWARM DETECTION"
              right={<Badge variant="info">IDLE</Badge>}
              testId="swarm-idle"
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: 14,
                }}
              >
                <VoicePulse size={140} label="LISTENING" color="var(--cyan)" />
              </div>
              <div
                className="mono"
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "rgba(255,255,255,0.8)",
                  textAlign: "center",
                  marginTop: 18,
                  lineHeight: 1.5,
                }}
              >
                Auto-trigger when ≥ 3 complaints cluster within ~500 m in the
                last 5 min.
                <br />
                <span style={{ color: "var(--cyan)", fontWeight: 700 }}>
                  SCAN INTERVAL: 10 s
                </span>
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

function ComplaintHeader({ total, en, kn, onSeed }) {
  return (
    <div
      className="panel"
      style={{
        padding: "16px 22px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 18,
        position: "relative",
        overflow: "hidden",
      }}
      data-testid="complaint-header"
    >
      <div>
        <div
          className="mono"
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: "var(--cyan)",
            letterSpacing: "0.28em",
            marginBottom: 6,
          }}
        >
          ▸ COMPLAINT FORUM
        </div>
        <div
          className="display"
          style={{
            fontSize: 28,
            fontWeight: 600,
            color: "var(--text)",
            letterSpacing: "0.06em",
            lineHeight: 1,
          }}
        >
          COMPLAINT{" "}
          <span
            style={{
              color: "var(--orange)",
              textShadow: "0 0 14px rgba(249,115,22,0.55)",
            }}
          >
            FORUM
          </span>
        </div>
        <div
          className="mono"
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "rgba(255,255,255,0.8)",
            marginTop: 8,
            maxWidth: 560,
            lineHeight: 1.5,
          }}
        >
          Drop a complaint in English or ಕನ್ನಡ — clusters auto-dispatch when the
          swarm threshold is crossed.
        </div>
      </div>
      <div style={{ display: "flex", gap: 22, alignItems: "center" }}>
        <Counter label="TOTAL" value={total} color="var(--orange)" />
        <Counter label="EN" value={en} color="var(--cyan)" />
        <Counter label="ಕನ್ನಡ" value={kn} color="#f97316" />
        <button
          onClick={onSeed}
          className="btn ghost"
          style={{ fontSize: 10, padding: "8px 12px" }}
          data-testid="seed-demo"
        >
          ▶ SEED SWARM
        </button>
      </div>
    </div>
  );
}

function Counter({ label, value, color }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div
        className="mono"
        style={{
          fontSize: 26,
          color,
          textShadow: `0 0 12px ${color}66`,
          lineHeight: 1,
        }}
      >
        <AnimatedNumber value={value} />
      </div>
      <div
        className="display"
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: "rgba(255,255,255,0.8)",
          letterSpacing: "0.18em",
          marginTop: 4,
        }}
      >
        {label}
      </div>
    </div>
  );
}
