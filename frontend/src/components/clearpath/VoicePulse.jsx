import { useEffect, useRef } from "react";

/**
 * VoicePulse — small Spline-style 3D widget representing citizen voice.
 * - A glowing core sphere with a stylised "signal antenna" rising.
 * - Concentric pulse rings emanate outward continuously.
 * - 6 audio-waveform bars surround it, modulating randomly.
 * - Cursor proximity tilts the rig; hover boosts amplitude.
 *
 * Pure SVG/CSS, no Three / Spline runtime. Sized 130-180px ideal.
 */
export default function VoicePulse({
  size = 160,
  label = "CITIZEN VOICE",
  color = "var(--cyan)",
}) {
  const wrapRef = useRef(null);
  const rigRef = useRef(null);
  const barRefs = useRef([]);

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
      rig.style.setProperty("--vp-tx", `${-dy * 12}deg`);
      rig.style.setProperty("--vp-ty", `${dx * 12}deg`);
    };
    window.addEventListener("mousemove", onMove);

    // randomize bar heights every 180ms
    const id = setInterval(() => {
      barRefs.current.forEach((el, i) => {
        if (!el) return;
        const base = 8 + Math.abs(Math.sin(Date.now() / 320 + i)) * 20;
        el.style.transform = `scaleY(${(base / 14).toFixed(2)})`;
      });
    }, 180);

    return () => {
      window.removeEventListener("mousemove", onMove);
      clearInterval(id);
    };
  }, []);

  const bars = 8;
  return (
    <div
      ref={wrapRef}
      data-testid="voice-pulse"
      style={{
        width: size,
        height: size,
        position: "relative",
        perspective: 900,
        userSelect: "none",
      }}
    >
      <span
        aria-hidden
        style={{
          position: "absolute",
          inset: -16,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${color}33 0%, transparent 65%)`,
          filter: "blur(10px)",
          pointerEvents: "none",
        }}
      />

      <span
        ref={rigRef}
        className="vp-rig"
        style={{
          display: "block",
          width: "100%",
          height: "100%",
          transformStyle: "preserve-3d",
          transition: "transform 0.4s cubic-bezier(0.16,1,0.3,1)",
        }}
      >
        <svg
          viewBox="-80 -80 160 160"
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            overflow: "visible",
          }}
        >
          <defs>
            <radialGradient id="vp-core">
              <stop offset="0%" stopColor="#fff" />
              <stop offset="35%" stopColor={color} />
              <stop offset="100%" stopColor="rgba(0,0,0,0)" />
            </radialGradient>
            <linearGradient id="vp-base" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.6" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* concentric pulse rings (4 staggered) */}
          {[0, 1, 2, 3].map((i) => (
            <circle
              key={i}
              cx="0"
              cy="0"
              r="20"
              fill="none"
              stroke={color}
              strokeWidth="1.2"
              className="vp-pulse"
              style={{ animationDelay: `${i * 0.6}s` }}
            />
          ))}

          {/* base disc */}
          <ellipse cx="0" cy="14" rx="34" ry="6" fill="url(#vp-base)" />

          {/* core sphere */}
          <circle
            cx="0"
            cy="0"
            r="18"
            fill="url(#vp-core)"
            className="vp-core"
          />
          {/* core highlight */}
          <circle cx="-6" cy="-6" r="4" fill="rgba(255,255,255,0.5)" />

          {/* mic stem */}
          <line
            x1="0"
            y1="-18"
            x2="0"
            y2="-34"
            stroke={color}
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <circle cx="0" cy="-38" r="3" fill={color} className="vp-blink" />

          {/* surrounding wave bars (rendered as scaling rectangles) */}
          {Array.from({ length: bars }).map((_, i) => {
            const a = (i / bars) * Math.PI * 2;
            const r = 50;
            const x = Math.cos(a) * r;
            const y = Math.sin(a) * r;
            return (
              <rect
                key={`bar-${i}`}
                ref={(el) => (barRefs.current[i] = el)}
                x={x - 1.4}
                y={y - 7}
                width="2.8"
                height="14"
                rx="1"
                fill={i % 2 === 0 ? color : "var(--orange)"}
                opacity="0.85"
                style={{
                  transformOrigin: `${x}px ${y}px`,
                  transition: "transform 0.18s ease",
                  filter: `drop-shadow(0 0 4px ${i % 2 === 0 ? color : "var(--orange)"})`,
                }}
              />
            );
          })}

          {/* hovering chips */}
          <g transform="translate(46 -54)">
            <rect
              x="-24"
              y="-7"
              width="48"
              height="14"
              rx="3"
              fill="rgba(10,14,22,0.85)"
              stroke={color}
              strokeWidth="0.6"
            />
            <text
              x="0"
              y="3"
              textAnchor="middle"
              fontFamily="Share Tech Mono, monospace"
              fontSize="7"
              fill={color}
            >
              EN · ಕನ್ನಡ
            </text>
          </g>
        </svg>
      </span>

      <span
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: -18,
          textAlign: "center",
          fontFamily: "var(--font-display)",
          fontSize: 10,
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
