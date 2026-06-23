/**
 * VulnerableZone.jsx — "Human Cost" Dashboard
 * With Spline animated gradient background
 */

import { useEffect, useRef, useState, useMemo } from "react";
import Spline from "@splinetool/react-spline";
import { getJSON } from "@/lib/api";

// ─── Real Bengaluru Vulnerable Zones ─────────────────────────────────────────
const ZONES = [
  {
    id: "vz-01",
    name: "Manipal Hospital",
    area: "Old Airport Rd",
    type: "hospital",
    lat: 12.9516,
    lng: 77.6482,
    radius_m: 800,
  },
  {
    id: "vz-02",
    name: "Fortis Hospital",
    area: "Bannerghatta Rd",
    type: "hospital",
    lat: 12.8994,
    lng: 77.598,
    radius_m: 800,
  },
  {
    id: "vz-03",
    name: "St. John's Medical College",
    area: "Koramangala",
    type: "hospital",
    lat: 12.925,
    lng: 77.6233,
    radius_m: 600,
  },
  {
    id: "vz-04",
    name: "Bowring & Lady Curzon Hospital",
    area: "Shivajinagar",
    type: "hospital",
    lat: 12.9795,
    lng: 77.6043,
    radius_m: 600,
  },
  {
    id: "vz-05",
    name: "Victoria Hospital",
    area: "Majestic",
    type: "hospital",
    lat: 12.9659,
    lng: 77.571,
    radius_m: 600,
  },
  {
    id: "vz-06",
    name: "NIMHANS",
    area: "Hosur Rd",
    type: "hospital",
    lat: 12.9404,
    lng: 77.5956,
    radius_m: 500,
  },
  {
    id: "vz-07",
    name: "Bishop Cotton Boys' School",
    area: "St. Mark's Rd",
    type: "school",
    lat: 12.9698,
    lng: 77.599,
    radius_m: 400,
  },
  {
    id: "vz-08",
    name: "National Public School",
    area: "Indiranagar",
    type: "school",
    lat: 12.9784,
    lng: 77.6408,
    radius_m: 400,
  },
  {
    id: "vz-09",
    name: "Delhi Public School",
    area: "Whitefield",
    type: "school",
    lat: 12.9698,
    lng: 77.7499,
    radius_m: 400,
  },
  {
    id: "vz-10",
    name: "Kendriya Vidyalaya",
    area: "Sadashivanagar",
    type: "school",
    lat: 13.0048,
    lng: 77.5762,
    radius_m: 400,
  },
  {
    id: "vz-11",
    name: "Central Fire Station",
    area: "Shivajinagar",
    type: "fire",
    lat: 12.982,
    lng: 77.601,
    radius_m: 300,
  },
  {
    id: "vz-12",
    name: "Basavanagudi Fire Station",
    area: "Basavanagudi",
    type: "fire",
    lat: 12.9442,
    lng: 77.57,
    radius_m: 300,
  },
];

const ZONE_META = {
  hospital: {
    color: "#ef4444",
    icon: "+",
    urgency: "CRITICAL",
    callout: (inc, zone) =>
      `A ${inc.event_cause?.replace(/_/g, " ")} is blocking access to ${zone.name}. Every minute it stays there, ambulances reroute through residential streets — adding 4 to 12 critical minutes to emergency response time.`,
    human: "ambulance rerouted",
  },
  school: {
    color: "#f59e0b",
    icon: "△",
    urgency: "ELEVATED",
    callout: (inc, zone) =>
      `A ${inc.event_cause?.replace(/_/g, " ")} near ${zone.name} during school hours puts hundreds of children in an unsheltered zone, waiting for pickup that cannot reach them.`,
    human: "children stranded",
  },
  fire: {
    color: "#06b6d4",
    icon: "⌖",
    urgency: "HIGH",
    callout: (inc, zone) =>
      `A ${inc.event_cause?.replace(/_/g, " ")} is blocking the ${zone.name} corridor. Every 60 seconds of delay doubles structural fire damage.`,
    human: "fire response delayed",
  },
};

function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.asin(Math.sqrt(a));
}

function tagIncidents(incidents) {
  return incidents
    .map((inc) => {
      const matches = [];
      for (const zone of ZONES) {
        const dist = haversine(inc.lat, inc.lng, zone.lat, zone.lng);
        if (dist * 1000 <= zone.radius_m) {
          matches.push({ ...zone, dist_m: Math.round(dist * 1000) });
        }
      }
      const priority = ["hospital", "fire", "school"];
      matches.sort(
        (a, b) => priority.indexOf(a.type) - priority.indexOf(b.type),
      );
      return { ...inc, contextZones: matches, primaryZone: matches[0] || null };
    })
    .filter((i) => i.primaryZone !== null);
}

// ─── Animated counter ─────────────────────────────────────────────────────────
function Counter({ value, duration = 1200, color }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let start = null;
    const step = (ts) => {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(eased * value));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [value, duration]);
  return <span style={{ color }}>{display}</span>;
}

// ─── Ticking elapsed time ─────────────────────────────────────────────────────
function ElapsedTicker({ startedAt }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const tick = () => setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;
  return (
    <span style={{ fontVariantNumeric: "tabular-nums" }}>
      {m > 0 ? `${m}m ` : ""}
      {s}s
    </span>
  );
}

// ─── Heartbeat line ───────────────────────────────────────────────────────────
function Heartbeat({ color = "#ef4444", width = 200, height = 40 }) {
  const points = [
    [0, 20],
    [30, 20],
    [40, 5],
    [50, 35],
    [60, 5],
    [70, 20],
    [100, 20],
    [110, 12],
    [120, 28],
    [130, 20],
    [200, 20],
  ]
    .map(([x, y]) => `${x},${y}`)
    .join(" ");
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{ overflow: "visible" }}
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{
          filter: `drop-shadow(0 0 4px ${color})`,
          strokeDasharray: 400,
          strokeDashoffset: 0,
          animation: "hbDraw 2s linear infinite",
        }}
      />
    </svg>
  );
}

// ─── Story card ───────────────────────────────────────────────────────────────
function StoryCard({ inc, index, isActive, onClick, mountTime }) {
  const meta = ZONE_META[inc.primaryZone.type];
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const incidentTime = useMemo(() => mountTime - Math.random() * 3600000, []);

  return (
    <div
      onClick={onClick}
      style={{
        position: "relative",
        cursor: "pointer",
        padding: "28px 32px",
        borderRadius: 2,
        border: `1px solid ${isActive ? meta.color : "rgba(255,255,255,0.06)"}`,
        borderLeft: `3px solid ${meta.color}`,
        background: isActive
          ? `linear-gradient(135deg, ${meta.color}0d 0%, transparent 60%)`
          : "rgba(0,0,0,0.35)",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
        transition: "all 0.35s cubic-bezier(0.16,1,0.3,1)",
        animation: `cardIn 0.5s ${index * 0.08}s both cubic-bezier(0.16,1,0.3,1)`,
      }}
    >
      {/* Zone badge */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 14,
        }}
      >
        <span style={{ fontSize: 18 }}>{meta.icon}</span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 9,
            letterSpacing: "0.2em",
            color: meta.color,
            fontWeight: 700,
            padding: "2px 8px",
            border: `1px solid ${meta.color}44`,
            borderRadius: 2,
            background: `${meta.color}11`,
          }}
        >
          {meta.urgency}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 9,
            letterSpacing: "0.12em",
            fontWeight: 600,
            color: "rgba(255,255,255,0.75)",
          }}
        >
          {inc.primaryZone.name.toUpperCase()} · {inc.primaryZone.dist_m}m
        </span>
        <span
          style={{
            marginLeft: "auto",
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: isActive ? meta.color : "rgba(255,255,255,0.25)",
          }}
        >
          <ElapsedTicker startedAt={incidentTime} />
        </span>
      </div>

      {/* Incident cause — big */}
      <div
        style={{
          fontSize: 26,
          fontWeight: 700,
          letterSpacing: "0.04em",
          fontWeight: 600,
          color: "rgba(255,255,255,0.92)",
          marginBottom: 8,
          fontFamily: "var(--font-display, var(--font-mono))",
          textTransform: "uppercase",
        }}
      >
        {inc.event_cause?.replace(/_/g, " ")}
      </div>

      {/* Location */}
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "rgba(255,255,255,0.8)",
          marginBottom: isActive ? 18 : 0,
          letterSpacing: "0.08em",
          fontWeight: 600,
        }}
      >
        {inc.corridor && inc.corridor !== "Non-corridor"
          ? inc.corridor
          : inc.primaryZone.area}{" "}
        · Bengaluru
      </div>

      {/* Expanded story */}
      {isActive && (
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 15,
            color: "rgba(255,255,255,0.65)",
            lineHeight: 1.75,
            borderTop: `1px solid ${meta.color}22`,
            paddingTop: 16,
            animation: "fadeUp 0.3s ease both",
          }}
        >
          {meta.callout(inc, inc.primaryZone)}
        </div>
      )}

      {/* Closure prob bar */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 2,
          background: "rgba(255,255,255,0.04)",
          borderRadius: "0 0 2px 2px",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.round((inc.closure_prob || 0) * 100)}%`,
            background: meta.color,
            borderRadius: "0 0 2px 2px",
            opacity: 0.6,
            transition: "width 1s ease",
          }}
        />
      </div>
    </div>
  );
}

// ─── Spline Background ────────────────────────────────────────────────────────
function SplineBackground() {
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
        overflow: "hidden",
      }}
    >
      {/* Spline scene */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          // Nudge slightly to hide the "Made with Spline" watermark at bottom-right
          transform: "scale(1.08)",
          transformOrigin: "center center",
        }}
      >
        <Spline
          scene="https://prod.spline.design/SinzWFzKI2N1ujUH/scene.splinecode"
          style={{ width: "100%", height: "100%" }}
        />
      </div>

      {/* Cover the "Made with Spline" badge in bottom-right corner */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          right: 0,
          width: 200,
          height: 56,
          background: "#020408",
          zIndex: 1,
        }}
      />

      {/* Dark overlay so the dashboard text stays readable */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(135deg, rgba(2,4,8,0.72) 0%, rgba(2,4,8,0.55) 50%, rgba(2,4,8,0.72) 100%)",
          zIndex: 2,
        }}
      />
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function VulnerableZone() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState(null);
  const [filterType, setFilterType] = useState("ALL");
  const [mounted] = useState(() => Date.now());
  const styleRef = useRef(false);

  useEffect(() => {
    if (styleRef.current) return;
    styleRef.current = true;
    const s = document.createElement("style");
    s.textContent = `
      @keyframes hbDraw {
        0%   { stroke-dashoffset: 400; opacity: 1; }
        70%  { stroke-dashoffset: 0;   opacity: 1; }
        100% { stroke-dashoffset: 0;   opacity: 0; }
      }
      @keyframes cardIn {
        from { opacity: 0; transform: translateY(16px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      @keyframes fadeUp {
        from { opacity: 0; transform: translateY(6px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      @keyframes pulseRing {
        0%   { transform: scale(1);   opacity: 0.6; }
        100% { transform: scale(2.2); opacity: 0; }
      }
      @keyframes scanLine {
        0%   { transform: translateY(-100%); }
        100% { transform: translateY(100vh); }
      }
      @keyframes heroIn {
        from { opacity: 0; transform: translateY(24px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      .vz-hero-stat { animation: heroIn 0.7s cubic-bezier(0.16,1,0.3,1) both; }
    `;
    document.head.appendChild(s);
  }, []);

  useEffect(() => {
    getJSON("/incidents")
      .then((data) => {
        setIncidents(tagIncidents(data));
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    if (filterType === "ALL") return incidents;
    return incidents.filter((i) => i.primaryZone?.type === filterType);
  }, [incidents, filterType]);

  const counts = useMemo(
    () => ({
      hospital: incidents.filter((i) => i.primaryZone?.type === "hospital")
        .length,
      school: incidents.filter((i) => i.primaryZone?.type === "school").length,
      fire: incidents.filter((i) => i.primaryZone?.type === "fire").length,
      total: incidents.length,
    }),
    [incidents],
  );

  const activeInc = activeId ? filtered.find((i) => i.id === activeId) : null;

  return (
    <div
      style={{
        minHeight: "calc(100vh - 49px)",
        position: "relative",
        overflow: "hidden",
        color: "#fff",
        // Fallback background in case Spline hasn't loaded yet
        background: "#020408",
      }}
    >
      {/* ── SPLINE BACKGROUND ─────────────────────────────────────────────── */}
      <SplineBackground />

      {/* Ambient scan line */}
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          height: "1px",
          background:
            "linear-gradient(90deg, transparent, rgba(239,68,68,0.15), transparent)",
          animation: "scanLine 8s linear infinite",
          zIndex: 3,
          pointerEvents: "none",
        }}
      />

      {/* ── HERO SECTION ─────────────────────────────────────────────────── */}
      <div
        style={{
          position: "relative",
          zIndex: 4,
          padding: "56px 64px 48px",
          borderBottom: "1px solid rgba(255,255,255,0.05)",
          display: "grid",
          gridTemplateColumns: "1fr auto",
          gap: 48,
          alignItems: "end",
          background: "rgba(2,4,8,0.3)",
          backdropFilter: "blur(2px)",
          WebkitBackdropFilter: "blur(2px)",
        }}
      >
        {/* Left: headline */}
        <div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              letterSpacing: "0.35em",
              fontWeight: 600,
              color: "rgba(239,68,68,0.7)",
              marginBottom: 20,
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "#ef4444",
                boxShadow: "0 0 8px #ef4444",
                animation: "pulseRing 1.4s ease-out infinite",
                display: "inline-block",
              }}
            />
            LIVE · BENGALURU ·{" "}
            {new Date().toLocaleTimeString("en-IN", {
              timeZone: "Asia/Kolkata",
              hour12: false,
            })}{" "}
            IST
          </div>

          <h1
            style={{
              margin: 0,
              fontSize: "clamp(36px, 5vw, 64px)",
              fontFamily: "var(--font-display, var(--font-mono))",
              fontWeight: 700,
              lineHeight: 1.05,
              letterSpacing: "-0.01em",
              color: "#fff",
            }}
          >
            {loading ? (
              "Scanning Bengaluru..."
            ) : counts.total === 0 ? (
              "All corridors clear."
            ) : (
              <>
                Right now,{" "}
                <span style={{ color: "#ef4444" }}>
                  {counts.hospital > 0 &&
                    `${counts.hospital} ambulance route${counts.hospital > 1 ? "s" : ""}`}
                  {counts.hospital > 0 && counts.school > 0 && " and "}
                  {counts.school > 0 &&
                    `${counts.school} school zone${counts.school > 1 ? "s" : ""}`}
                </span>{" "}
                in Bengaluru {counts.total === 1 ? "is" : "are"} blocked.
              </>
            )}
          </h1>

          <p
            style={{
              marginTop: 20,
              fontSize: 17,
              fontFamily: "var(--font-mono)",
              color: "rgba(255,255,255,0.8)",
              maxWidth: 560,
              lineHeight: 1.65,
            }}
          >
            Standard traffic AI counts cars on the road. ClearPath OS asks who
            is inside them.
          </p>
        </div>

        {/* Right: stat cluster */}
        {!loading && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 20,
              alignItems: "flex-end",
            }}
          >
            <Heartbeat color="#ef4444" width={160} height={36} />
            <div style={{ display: "flex", gap: 32 }}>
              {[
                {
                  n: counts.hospital,
                  label: "HOSPITAL\nCORRIDORS",
                  color: "#ef4444",
                  delay: "0.1s",
                },
                {
                  n: counts.school,
                  label: "SCHOOL\nZONES",
                  color: "#f59e0b",
                  delay: "0.2s",
                },
                {
                  n: counts.fire,
                  label: "FIRE\nCORRIDORS",
                  color: "#06b6d4",
                  delay: "0.3s",
                },
              ].map(({ n, label, color, delay }) => (
                <div
                  key={label}
                  className="vz-hero-stat"
                  style={{ animationDelay: delay, textAlign: "right" }}
                >
                  <div
                    style={{
                      fontSize: 48,
                      fontWeight: 800,
                      lineHeight: 1,
                      fontFamily: "var(--font-mono)",
                      color: n > 0 ? color : "rgba(255,255,255,0.1)",
                      textShadow: n > 0 ? `0 0 40px ${color}66` : "none",
                    }}
                  >
                    <Counter
                      value={n}
                      color={n > 0 ? color : "rgba(255,255,255,0.1)"}
                    />
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 8,
                      letterSpacing: "0.2em",
                      fontWeight: 600,
                      color: "rgba(255,255,255,0.88)",
                      marginTop: 4,
                      whiteSpace: "pre-line",
                      textAlign: "right",
                    }}
                  >
                    {label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── BODY ─────────────────────────────────────────────────────────── */}
      <div
        style={{
          position: "relative",
          zIndex: 4,
          display: "grid",
          gridTemplateColumns: activeInc ? "1fr 420px" : "1fr",
          minHeight: "calc(100vh - 300px)",
          transition: "grid-template-columns 0.4s cubic-bezier(0.16,1,0.3,1)",
        }}
      >
        {/* Left: story feed */}
        <div style={{ padding: "0 64px 64px" }}>
          {/* Filter bar */}
          <div
            style={{
              display: "flex",
              gap: 8,
              padding: "28px 0 24px",
              borderBottom: "1px solid rgba(255,255,255,0.05)",
              marginBottom: 24,
            }}
          >
            {[
              { key: "ALL", label: `ALL  ·  ${counts.total}`, color: "#fff" },
              {
                key: "hospital",
                label: `+  HOSPITAL  ·  ${counts.hospital}`,
                color: "#ef4444",
              },
              {
                key: "school",
                label: `△  SCHOOL  ·  ${counts.school}`,
                color: "#f59e0b",
              },
              {
                key: "fire",
                label: `⌖   FIRE  ·  ${counts.fire}`,
                color: "#06b6d4",
              },
            ].map(({ key, label, color }) => (
              <button
                key={key}
                onClick={() => {
                  setFilterType(key);
                  setActiveId(null);
                }}
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: "0.15em",
                  fontWeight: 600,
                  padding: "7px 16px",
                  borderRadius: 2,
                  cursor: "pointer",
                  border: "none",
                  background:
                    filterType === key ? `${color}18` : "rgba(0,0,0,0.3)",
                  color: filterType === key ? color : "rgba(255,255,255,0.3)",
                  outline:
                    filterType === key
                      ? `1px solid ${color}44`
                      : "1px solid rgba(255,255,255,0.08)",
                  transition: "all 0.2s ease",
                  backdropFilter: "blur(3px)",
                  WebkitBackdropFilter: "blur(3px)",
                }}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Cards */}
          {loading ? (
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                color: "rgba(255,255,255,0.88)",
                letterSpacing: "0.2em",
                fontWeight: 600,
                padding: "60px 0",
                textAlign: "center",
              }}
            >
              SCANNING INCIDENT DATABASE...
            </div>
          ) : filtered.length === 0 ? (
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 15,
                color: "rgba(255,255,255,0.88)",
                letterSpacing: "0.15em",
                fontWeight: 600,
                padding: "80px 0",
                textAlign: "center",
                lineHeight: 2,
              }}
            >
              NO FLAGGED INCIDENTS
              <br />
              <span style={{ fontSize: 10, opacity: 0.5 }}>
                All vulnerable zones clear
              </span>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {filtered.map((inc, i) => (
                <StoryCard
                  key={inc.id}
                  inc={inc}
                  index={i}
                  isActive={activeId === inc.id}
                  onClick={() =>
                    setActiveId(activeId === inc.id ? null : inc.id)
                  }
                  mountTime={mounted}
                />
              ))}
            </div>
          )}
        </div>

        {/* Right: deep dive panel (slides in) */}
        {activeInc &&
          (() => {
            const meta = ZONE_META[activeInc.primaryZone.type];
            return (
              <div
                style={{
                  borderLeft: "1px solid rgba(255,255,255,0.06)",
                  padding: "40px 36px",
                  position: "sticky",
                  top: 49,
                  height: "calc(100vh - 49px)",
                  overflowY: "auto",
                  animation: "cardIn 0.35s cubic-bezier(0.16,1,0.3,1) both",
                  background: `linear-gradient(180deg, rgba(2,4,8,0.7) 0%, rgba(2,4,8,0.55) 40%)`,
                  backdropFilter: "blur(16px)",
                  WebkitBackdropFilter: "blur(16px)",
                }}
              >
                {/* Zone icon + name */}
                <div style={{ fontSize: 40, marginBottom: 16 }}>
                  {meta.icon}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 9,
                    letterSpacing: "0.25em",
                    fontWeight: 600,
                    color: meta.color,
                    marginBottom: 6,
                  }}
                >
                  {meta.urgency} ZONE
                </div>
                <div
                  style={{
                    fontSize: 20,
                    fontWeight: 700,
                    fontFamily: "var(--font-display, var(--font-mono))",
                    color: "#fff",
                    marginBottom: 4,
                  }}
                >
                  {activeInc.primaryZone.name}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "rgba(255,255,255,0.8)",
                    marginBottom: 32,
                  }}
                >
                  {activeInc.primaryZone.area} · {activeInc.primaryZone.dist_m}m
                  from incident
                </div>

                {/* The human cost statement */}
                <div
                  style={{
                    fontSize: 14,
                    lineHeight: 1.8,
                    color: "rgba(255,255,255,0.88)",
                    fontFamily: "var(--font-mono)",
                    padding: "20px 0",
                    borderTop: `1px solid ${meta.color}22`,
                    borderBottom: `1px solid ${meta.color}22`,
                    marginBottom: 28,
                  }}
                >
                  {meta.callout(activeInc, activeInc.primaryZone)}
                </div>

                {/* Stats */}
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 14 }}
                >
                  {[
                    {
                      label: "INCIDENT TYPE",
                      value: activeInc.event_cause
                        ?.replace(/_/g, " ")
                        .toUpperCase(),
                    },
                    {
                      label: "CLOSURE PROBABILITY",
                      value: `${Math.round((activeInc.closure_prob || 0) * 100)}%`,
                      color: meta.color,
                    },
                    {
                      label: "EST. DURATION",
                      value: activeInc.duration_display || "—",
                    },
                    { label: "CORRIDOR", value: activeInc.corridor || "—" },
                    { label: "INCIDENT ID", value: activeInc.id, muted: true },
                  ].map(({ label, value, color, muted }) => (
                    <div
                      key={label}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "baseline",
                        gap: 12,
                        paddingBottom: 12,
                        borderBottom: "1px solid rgba(255,255,255,0.04)",
                      }}
                    >
                      <span
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 9,
                          letterSpacing: "0.18em",
                          fontWeight: 600,
                          color: "rgba(255,255,255,0.88)",
                        }}
                      >
                        {label}
                      </span>
                      <span
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 12,
                          color:
                            color ||
                            (muted
                              ? "rgba(255,255,255,0.25)"
                              : "rgba(255,255,255,0.85)"),
                          textAlign: "right",
                        }}
                      >
                        {value}
                      </span>
                    </div>
                  ))}
                </div>

                {/* All affected zones */}
                {activeInc.contextZones.length > 1 && (
                  <div style={{ marginTop: 28 }}>
                    <div
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 9,
                        letterSpacing: "0.2em",
                        fontWeight: 600,
                        color: "rgba(255,255,255,0.88)",
                        marginBottom: 12,
                      }}
                    >
                      ALL AFFECTED ZONES
                    </div>
                    {activeInc.contextZones.map((zone) => {
                      const m = ZONE_META[zone.type];
                      return (
                        <div
                          key={zone.id}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            marginBottom: 8,
                          }}
                        >
                          <span style={{ fontSize: 14 }}>{m.icon}</span>
                          <span
                            style={{
                              fontFamily: "var(--font-mono)",
                              fontSize: 11,
                              color: "rgba(255,255,255,0.82)",
                              flex: 1,
                            }}
                          >
                            {zone.name}
                          </span>
                          <span
                            style={{
                              fontFamily: "var(--font-mono)",
                              fontSize: 9,
                              color: m.color,
                            }}
                          >
                            {zone.dist_m}m
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })()}
      </div>

      {/* ── BOTTOM STATEMENT ─────────────────────────────────────────────── */}
      <div
        style={{
          position: "relative",
          zIndex: 4,
          padding: "48px 64px",
          borderTop: "1px solid rgba(255,255,255,0.05)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "rgba(2,4,8,0.3)",
          backdropFilter: "blur(2px)",
          WebkitBackdropFilter: "blur(2px)",
        }}
      >
        <div
          style={{
            fontFamily: "var(--font-display, var(--font-mono))",
            fontSize: "clamp(20px, 3vw, 36px)",
            fontWeight: 700,
            letterSpacing: "0.02em",
            fontWeight: 600,
            color: "rgba(255,255,255,0.35)",
            maxWidth: 700,
            lineHeight: 1.2,
          }}
        >
          Standard AI counts cars.
          <span style={{ color: "rgba(255,255,255,0.85)" }}>
            {" "}
            ClearPath OS counts lives.
          </span>
        </div>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            letterSpacing: "0.2em",
            fontWeight: 600,
            color: "rgba(255,255,255,0.65)",
            textAlign: "right",
            lineHeight: 1.8,
          }}
        >
          {ZONES.filter((z) => z.type === "hospital").length} HOSPITALS
          MONITORED
          <br />
          {ZONES.filter((z) => z.type === "school").length} SCHOOL ZONES
          MONITORED
          <br />
          {ZONES.filter((z) => z.type === "fire").length} FIRE CORRIDORS
          MONITORED
        </div>
      </div>
    </div>
  );
}
