import { useEffect, useState } from "react";

// Semicircular gauge. value: 0-100
export default function Gauge({ value = 0, size = 220, label = "", testId }) {
    const [v, setV] = useState(0);
    useEffect(() => {
        const t = setTimeout(() => setV(Math.max(0, Math.min(100, value))), 120);
        return () => clearTimeout(t);
    }, [value]);

    const r = size / 2 - 18;
    const cx = size / 2;
    const cy = size / 2 + 4;
    const angle = (v / 100) * 180 - 180; // -180 .. 0
    const rad = (angle * Math.PI) / 180;
    const nx = cx + r * Math.cos(rad);
    const ny = cy + r * Math.sin(rad);

    const arcs = [
        { from: -180, to: -108, color: "var(--green)" }, // 0-40
        { from: -108, to: -36, color: "var(--amber)" }, // 40-80
        { from: -36, to: 0, color: "var(--red)" }, // 80-100
    ];

    const arcPath = (a1, a2) => {
        const p1 = polar(cx, cy, r, a1);
        const p2 = polar(cx, cy, r, a2);
        const large = a2 - a1 > 180 ? 1 : 0;
        return `M ${p1.x} ${p1.y} A ${r} ${r} 0 ${large} 1 ${p2.x} ${p2.y}`;
    };

    return (
        <div data-testid={testId} style={{ position: "relative" }}>
            <svg width={size} height={size / 2 + 30} viewBox={`0 0 ${size} ${size / 2 + 30}`}>
                <defs>
                    <filter id="glow"><feGaussianBlur stdDeviation="2" /></filter>
                </defs>
                {arcs.map((a, i) => (
                    <path
                        key={i}
                        d={arcPath(a.from, a.to)}
                        fill="none"
                        stroke={a.color}
                        strokeWidth={10}
                        strokeLinecap="butt"
                        opacity={0.85}
                    />
                ))}
                {/* tick marks */}
                {[0, 20, 40, 60, 80, 100].map((t) => {
                    const ang = (t / 100) * 180 - 180;
                    const a = polar(cx, cy, r - 10, ang);
                    const b = polar(cx, cy, r + 10, ang);
                    return (
                        <line
                            key={t}
                            x1={a.x}
                            y1={a.y}
                            x2={b.x}
                            y2={b.y}
                            stroke="rgba(148,163,184,0.4)"
                            strokeWidth="1"
                        />
                    );
                })}
                {/* needle */}
                <line
                    x1={cx}
                    y1={cy}
                    x2={nx}
                    y2={ny}
                    stroke="var(--orange)"
                    strokeWidth="3"
                    strokeLinecap="round"
                    style={{ transition: "all 1.2s cubic-bezier(0.16,1,0.3,1)", filter: "drop-shadow(0 0 6px rgba(249,115,22,0.9))" }}
                />
                <circle cx={cx} cy={cy} r={7} fill="#030712" stroke="var(--orange)" strokeWidth="2" />
            </svg>
            <div
                style={{
                    position: "absolute",
                    left: 0,
                    right: 0,
                    bottom: 0,
                    textAlign: "center",
                }}
            >
                <div
                    className="mono"
                    style={{
                        fontSize: 32,
                        color: "var(--orange)",
                        textShadow: "0 0 12px rgba(249,115,22,0.6)",
                    }}
                >
                    {Math.round(v)}%
                </div>
                <div
                    className="display"
                    style={{ fontSize: 10, color: "var(--text-mute)", letterSpacing: "0.18em" }}
                >
                    {label}
                </div>
            </div>
        </div>
    );
}
function polar(cx, cy, r, deg) {
    const rad = (deg * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}
