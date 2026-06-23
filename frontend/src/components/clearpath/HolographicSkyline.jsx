import { useEffect, useRef } from "react";
import { ASSET_TYPES } from "./SimulateTab";

/**
 * HolographicSkyline — a horizontal isometric strip that renders every
 * placed asset as a 3D building. Height = reduction rate * scale.
 * Hover highlights the asset on the city-health side. Click removes it.
 * Tracks count + emits a soft pulse on each placement.
 *
 * Pure SVG. Animates entry, hover, exit. No three / spline runtime.
 */
export default function HolographicSkyline({
  placedAssets,
  onRemove,
  simulationResult,
  onHover,
}) {
  const wrapRef = useRef(null);
  const sortedAssets = placedAssets;
  const showCount = sortedAssets.length;
  const empty = showCount === 0;

  // ground grid lines that sweep across — driven by CSS
  return (
    <div
      ref={wrapRef}
      data-testid="holographic-skyline"
      style={{
        position: "relative",
        width: "100%",
        background:
          "linear-gradient(180deg, rgba(6,182,212,0.06), rgba(3,7,18,0.65))",
        borderTop: "1px solid var(--border)",
        borderBottom: "1px solid var(--border)",
        overflow: "hidden",
        userSelect: "none",
      }}
    >
      {/* Sweep grid */}
      <svg
        aria-hidden
        viewBox="0 0 600 80"
        preserveAspectRatio="none"
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
        }}
      >
        <defs>
          <linearGradient id="skyglow" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="rgba(249,115,22,0.6)" />
            <stop offset="100%" stopColor="rgba(249,115,22,0)" />
          </linearGradient>
          <linearGradient id="hgrid" x1="0" x2="1">
            <stop offset="0%" stopColor="rgba(6,182,212,0.0)" />
            <stop offset="50%" stopColor="rgba(6,182,212,0.18)" />
            <stop offset="100%" stopColor="rgba(6,182,212,0.0)" />
          </linearGradient>
        </defs>
        {/* horizon glow */}
        <rect
          x="0"
          y="48"
          width="600"
          height="32"
          fill="url(#skyglow)"
          opacity="0.5"
        />
        {/* horizontal scan lines */}
        {Array.from({ length: 6 }).map((_, i) => (
          <line
            key={`hh${i}`}
            x1="0"
            x2="600"
            y1={56 + i * 4}
            y2={56 + i * 4}
            stroke="url(#hgrid)"
            strokeWidth="0.5"
          />
        ))}
        {/* vertical perspective lines */}
        {[100, 200, 300, 400, 500].map((x) => (
          <line
            key={`hv${x}`}
            x1={x}
            y1="56"
            x2={x + (x - 300) * 0.6}
            y2="80"
            stroke="rgba(6,182,212,0.12)"
            strokeWidth="0.4"
          />
        ))}
        <line
          x1="0"
          y1="56"
          x2="600"
          y2="56"
          stroke="rgba(249,115,22,0.45)"
          strokeWidth="0.6"
        />

        {/* sweeping radar bar */}
        <rect
          x="-40"
          y="0"
          width="40"
          height="80"
          fill="url(#skyglow)"
          opacity="0.35"
          className="sky-sweep"
        />
      </svg>

      {/* HEADER */}
      <div
        style={{
          position: "relative",
          display: "flex",
          justifyContent: "space-between",
          padding: "6px 12px",
          zIndex: 2,
        }}
      >
        <span
          className="display"
          style={{
            fontSize: 10,
            letterSpacing: "0.18em",
            color: "var(--cyan)",
          }}
        >
          ◢ HOLOGRAPHIC SKYLINE
        </span>
        <span
          className="mono"
          style={{ fontSize: 10, color: "var(--text-mute)" }}
        >
          {showCount} ASSET{showCount !== 1 ? "S" : ""} PLACED
        </span>
      </div>

      {/* SKYLINE CANVAS */}
      <div
        style={{
          position: "relative",
          height: 110,
          padding: "0 14px",
          display: "flex",
          alignItems: "flex-end",
          gap: 10,
          zIndex: 2,
          overflowX: "auto",
          overflowY: "hidden",
        }}
      >
        {empty && (
          <div
            className="mono"
            style={{
              width: "100%",
              textAlign: "center",
              color: "var(--text-mute)",
              fontSize: 11,
              paddingBottom: 30,
            }}
          >
            Select an asset, click the map — your skyline rises here.
          </div>
        )}

        {sortedAssets.map((a, idx) => {
          const meta = ASSET_TYPES[a.type];
          const h = 24 + a.reduction_rate * 60; // 24px - 84px
          const w = 22 + meta.radius_km * 4; // wider for larger radius
          return (
            <button
              key={a.id}
              onMouseEnter={() => onHover?.(a.id)}
              onMouseLeave={() => onHover?.(null)}
              onClick={() => onRemove(a.id)}
              className="sky-tower"
              data-testid={`skyline-tower-${a.id}`}
              style={{
                position: "relative",
                background: "transparent",
                border: "none",
                padding: 0,
                animationDelay: `${idx * 0.08}s`,
                cursor: "pointer",
              }}
              title={`${meta.name} · ${Math.round(a.reduction_rate * 100)}% · click to remove`}
            >
              <svg
                width={w + 12}
                height={h + 18}
                viewBox={`0 0 ${w + 12} ${h + 18}`}
              >
                {/* iso prism */}
                {/* top */}
                <polygon
                  points={`0,8 ${w / 2},0 ${w + 10},8 ${w / 2 + 10},16`}
                  fill={`${meta.color}66`}
                  stroke={meta.color}
                  strokeWidth="0.8"
                />
                {/* front */}
                <polygon
                  points={`0,8 ${w / 2 + 10},16 ${w / 2 + 10},${h + 16} 0,${h + 8}`}
                  fill={`${meta.color}22`}
                  stroke={meta.color}
                  strokeWidth="0.8"
                />
                {/* right */}
                <polygon
                  points={`${w / 2 + 10},16 ${w + 10},8 ${w + 10},${h + 8} ${w / 2 + 10},${h + 16}`}
                  fill={`${meta.color}10`}
                  stroke={meta.color}
                  strokeWidth="0.8"
                />
                {/* windows — animated by translateY */}
                {Array.from({ length: Math.floor(h / 10) }).map((_, i) => (
                  <line
                    key={i}
                    x1={4}
                    y1={16 + i * 10}
                    x2={w / 2 + 6}
                    y2={20 + i * 10}
                    stroke={meta.color}
                    strokeWidth="0.6"
                    opacity={0.55}
                  />
                ))}
                {/* nav-light */}
                <circle
                  cx={w / 2 + 5}
                  cy={2}
                  r="2"
                  fill="#fff"
                  className="sky-blink"
                  style={{ filter: `drop-shadow(0 0 6px ${meta.color})` }}
                />
                {/* base shadow */}
                <ellipse
                  cx={w / 2 + 5}
                  cy={h + 14}
                  rx={w / 2 + 4}
                  ry="2"
                  fill={meta.color}
                  opacity="0.35"
                />
              </svg>
              {/* mini label under tower */}
              <div
                className="mono"
                style={{
                  position: "absolute",
                  bottom: -2,
                  left: 0,
                  right: 0,
                  textAlign: "center",
                  fontSize: 8,
                  color: meta.color,
                  letterSpacing: "0.05em",
                }}
              >
                {Math.round(a.reduction_rate * 100)}%
              </div>
            </button>
          );
        })}
      </div>

      {/* FOOT META */}
      {simulationResult && !simulationResult.error && (
        <div
          className="fade-in"
          style={{
            position: "relative",
            display: "flex",
            justifyContent: "space-between",
            padding: "4px 12px",
            borderTop: "1px solid var(--border)",
            zIndex: 2,
            background: "rgba(16,185,129,0.04)",
          }}
        >
          <span
            className="mono"
            style={{ fontSize: 10, color: "var(--green)" }}
          >
            ✓ SIMULATED · GR {simulationResult.gr_score?.toFixed(1) || 0}%
          </span>
          <span className="mono" style={{ fontSize: 10, color: "var(--cyan)" }}>
            {Number(simulationResult.incidents_affected || 0).toLocaleString()}{" "}
            INCIDENTS RESOLVED
          </span>
        </div>
      )}
    </div>
  );
}
