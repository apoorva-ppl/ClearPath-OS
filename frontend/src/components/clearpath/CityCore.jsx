import { useEffect, useRef } from "react";

/**
 * CityCore — small Spline-style 3D city widget (pure SVG/CSS, no runtime).
 * - Isometric hex pad with 5 buildings of varying height rising from it.
 * - Slow continuous yaw rotation, cursor proximity adds tilt.
 * - Pulsing rooftop nav-lights synced with the orange power band.
 * - Sized 110–140px ideal — drop as a header accent / status badge.
 */
export default function CityCore({ size = 130, label = "URBAN ARCHITECT" }) {
  const wrapRef = useRef(null);
  const rigRef = useRef(null);

  useEffect(() => {
    const wrap = wrapRef.current;
    const rig = rigRef.current;
    if (!wrap || !rig) return;
    const onMove = (e) => {
      const r = wrap.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dx = Math.max(-1, Math.min(1, (e.clientX - cx) / 220));
      const dy = Math.max(-1, Math.min(1, (e.clientY - cy) / 220));
      rig.style.setProperty("--tx", `${-dy * 14}deg`);
      rig.style.setProperty("--ty", `${dx * 14}deg`);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  const buildings = [
    { x: -22, w: 14, h: 36, color: "#f97316", lite: true },
    { x: -4, w: 12, h: 24, color: "#06b6d4" },
    { x: 14, w: 16, h: 42, color: "#fbbf24", lite: true },
    { x: -38, w: 10, h: 18, color: "#10b981" },
    { x: 30, w: 11, h: 22, color: "#06b6d4", lite: true },
  ];

  return (
    <div
      ref={wrapRef}
      data-testid="city-core"
      style={{
        width: size,
        height: size,
        position: "relative",
        perspective: 900,
        userSelect: "none",
        pointerEvents: "auto",
      }}
    >
      {/* halo */}
      <span
        aria-hidden
        style={{
          position: "absolute",
          inset: -14,
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(249,115,22,0.28) 0%, rgba(6,182,212,0.16) 38%, transparent 70%)",
          filter: "blur(10px)",
          pointerEvents: "none",
        }}
      />

      <span
        ref={rigRef}
        className="cc-rig"
        style={{
          display: "block",
          width: "100%",
          height: "100%",
          transformStyle: "preserve-3d",
          transition: "transform 0.5s cubic-bezier(0.16,1,0.3,1)",
        }}
      >
        <svg
          viewBox="-70 -70 140 140"
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            overflow: "visible",
          }}
        >
          <defs>
            <linearGradient id="cc-pad" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="rgba(249,115,22,0.6)" />
              <stop offset="100%" stopColor="rgba(249,115,22,0.08)" />
            </linearGradient>
            <linearGradient id="cc-grid" x1="0" x2="1">
              <stop offset="0%" stopColor="rgba(6,182,212,0.05)" />
              <stop offset="50%" stopColor="rgba(6,182,212,0.5)" />
              <stop offset="100%" stopColor="rgba(6,182,212,0.05)" />
            </linearGradient>
          </defs>

          <g className="cc-spin">
            {/* Iso ground hexagon */}
            <polygon
              points="-46,0 -23,14 23,14 46,0 23,-14 -23,-14"
              fill="url(#cc-pad)"
              stroke="var(--orange)"
              strokeWidth="1.2"
              opacity="0.9"
            />
            {/* grid lines on pad */}
            {[-1, 0, 1].map((i) => (
              <line
                key={`gv${i}`}
                x1={i * 15}
                y1="-14"
                x2={i * 15}
                y2="14"
                stroke="url(#cc-grid)"
                strokeWidth="0.5"
              />
            ))}
            {[-1, 0, 1].map((i) => (
              <line
                key={`gh${i}`}
                x1="-46"
                y1={i * 7}
                x2="46"
                y2={i * 7}
                stroke="url(#cc-grid)"
                strokeWidth="0.5"
              />
            ))}

            {/* Buildings — drawn as iso prisms (top quad + right face + front face) */}
            {buildings.map((b, idx) => {
              const x = b.x;
              const w = b.w;
              const h = b.h;
              // base of building roughly at z=0 (y=0 in iso). Top is at y = -h.
              const top = `${x - w / 2},${-h - 4} ${x + w / 2},${-h - 8} ${x + w / 2 + 4},${-h - 4} ${x - w / 2 + 4},${-h}`;
              const right = `${x + w / 2},${-h - 8} ${x + w / 2 + 4},${-h - 4} ${x + w / 2 + 4},${4} ${x + w / 2},${0}`;
              const front = `${x - w / 2},${-h - 4} ${x + w / 2},${-h - 8} ${x + w / 2},${0} ${x - w / 2},${4}`;
              return (
                <g key={idx}>
                  <polygon
                    points={front}
                    fill={`${b.color}28`}
                    stroke={b.color}
                    strokeWidth="0.6"
                  />
                  <polygon
                    points={right}
                    fill={`${b.color}18`}
                    stroke={b.color}
                    strokeWidth="0.6"
                  />
                  <polygon
                    points={top}
                    fill={`${b.color}40`}
                    stroke={b.color}
                    strokeWidth="0.7"
                  />
                  {/* nav light on roof */}
                  {b.lite && (
                    <circle
                      cx={x + 2}
                      cy={-h - 4}
                      r="1.6"
                      fill="#fff"
                      className="cc-blink"
                      style={{ filter: `drop-shadow(0 0 6px ${b.color})` }}
                    />
                  )}
                </g>
              );
            })}

            {/* hovering chip */}
            <g transform="translate(36 -52)">
              <rect
                x="-22"
                y="-7"
                width="44"
                height="14"
                rx="3"
                fill="rgba(10,14,22,0.8)"
                stroke="var(--orange)"
                strokeWidth="0.6"
              />
              <text
                x="0"
                y="3"
                textAnchor="middle"
                fontFamily="Share Tech Mono, monospace"
                fontSize="7"
                fill="var(--orange)"
                letterSpacing="0.2"
              >
                +1 HUB
              </text>
            </g>
          </g>

          {/* horizon ring */}
          <ellipse
            cx="0"
            cy="0"
            rx="56"
            ry="18"
            fill="none"
            stroke="rgba(249,115,22,0.45)"
            strokeWidth="0.7"
            strokeDasharray="3 5"
            className="cc-ring"
          />
        </svg>
      </span>

      <span
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: -16,
          textAlign: "center",
          fontFamily: "var(--font-display)",
          fontSize: 9,
          letterSpacing: "0.22em",
          color: "var(--text-mute)",
          textTransform: "uppercase",
          pointerEvents: "none",
        }}
      >
        {label}
      </span>
    </div>
  );
}
