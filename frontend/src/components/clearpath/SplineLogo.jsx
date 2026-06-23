import { useEffect, useRef } from "react";

/**
 * Spline-inspired 3D-ish logo. Pure CSS/SVG/canvas, no Spline runtime.
 * - A rotating wireframe sphere (CSS 3D) wrapped by an orbiting torus ring.
 * - Inside, a soft gradient core with kinetic noise overlay.
 * - On hover, the whole rig parallaxes toward the cursor.
 */
export default function SplineLogo({ size = 380 }) {
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
            const dx = (e.clientX - cx) / r.width;
            const dy = (e.clientY - cy) / r.height;
            rig.style.transform = `rotateY(${dx * 22}deg) rotateX(${-dy * 22}deg)`;
        };
        const onLeave = () => {
            rig.style.transform = "rotateY(0deg) rotateX(0deg)";
        };
        window.addEventListener("mousemove", onMove);
        wrap.addEventListener("mouseleave", onLeave);
        return () => {
            window.removeEventListener("mousemove", onMove);
            wrap.removeEventListener("mouseleave", onLeave);
        };
    }, []);

    // Build sphere wireframe lines
    const lats = 9;
    const longs = 14;
    return (
        <div
            ref={wrapRef}
            style={{
                width: size,
                height: size,
                position: "relative",
                perspective: 1100,
                pointerEvents: "auto",
            }}
            data-testid="spline-logo"
        >
            {/* radial glow halo */}
            <div
                style={{
                    position: "absolute",
                    inset: -60,
                    background:
                        "radial-gradient(circle, rgba(249,115,22,0.25) 0%, rgba(6,182,212,0.12) 38%, transparent 70%)",
                    filter: "blur(20px)",
                    pointerEvents: "none",
                }}
            />

            <div
                ref={rigRef}
                style={{
                    width: "100%",
                    height: "100%",
                    transformStyle: "preserve-3d",
                    transition: "transform 0.6s cubic-bezier(0.16,1,0.3,1)",
                    position: "relative",
                }}
            >
                {/* gradient core */}
                <div
                    className="logo-core"
                    style={{
                        position: "absolute",
                        left: "20%",
                        top: "20%",
                        width: "60%",
                        height: "60%",
                        borderRadius: "50%",
                        background:
                            "radial-gradient(circle at 35% 30%, #fff7ed 0%, #f97316 18%, #c2410c 44%, #7c2d12 70%, #1c1917 100%)",
                        boxShadow:
                            "0 0 60px rgba(249,115,22,0.55), inset -22px -22px 60px rgba(0,0,0,0.6), inset 18px 18px 36px rgba(255,200,150,0.18)",
                        transform: "translateZ(0px)",
                    }}
                />

                {/* wireframe sphere */}
                <svg
                    viewBox="-110 -110 220 220"
                    style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
                >
                    <defs>
                        <radialGradient id="lineGrad" cx="50%" cy="50%" r="50%">
                            <stop offset="0%" stopColor="rgba(6,182,212,0.85)" />
                            <stop offset="100%" stopColor="rgba(6,182,212,0.15)" />
                        </radialGradient>
                        <linearGradient id="ringGrad" x1="0" x2="1">
                            <stop offset="0%" stopColor="#f97316" />
                            <stop offset="50%" stopColor="#fbbf24" />
                            <stop offset="100%" stopColor="#06b6d4" />
                        </linearGradient>
                    </defs>

                    {/* Latitude ellipses */}
                    {Array.from({ length: lats }).map((_, i) => {
                        const t = (i + 1) / (lats + 1);
                        const rx = 100;
                        const ry = 100 * Math.sin(t * Math.PI);
                        const y = -100 * Math.cos(t * Math.PI);
                        return (
                            <ellipse
                                key={`lat-${i}`}
                                cx="0"
                                cy={y}
                                rx={rx * Math.sin(t * Math.PI)}
                                ry={ry * 0.18}
                                fill="none"
                                stroke="url(#lineGrad)"
                                strokeWidth="0.6"
                                opacity={0.6}
                            />
                        );
                    })}

                    {/* Longitude ellipses (rotated around Y) */}
                    {Array.from({ length: longs }).map((_, i) => {
                        const angle = (i / longs) * 180;
                        return (
                            <ellipse
                                key={`lng-${i}`}
                                cx="0"
                                cy="0"
                                rx={100 * Math.abs(Math.sin((angle * Math.PI) / 180))}
                                ry="100"
                                fill="none"
                                stroke="url(#lineGrad)"
                                strokeWidth="0.5"
                                opacity={0.5}
                            />
                        );
                    })}

                    {/* Orbiting nodes */}
                    <g className="orbit-spin">
                        {Array.from({ length: 8 }).map((_, i) => {
                            const a = (i / 8) * Math.PI * 2;
                            const r = 105;
                            return (
                                <circle
                                    key={i}
                                    cx={Math.cos(a) * r}
                                    cy={Math.sin(a) * r * 0.3}
                                    r="2.4"
                                    fill="#fbbf24"
                                    style={{ filter: "drop-shadow(0 0 6px #fbbf24)" }}
                                />
                            );
                        })}
                    </g>
                </svg>

                {/* Orbiting outer ring (CSS 3D) */}
                <div
                    className="orbit-ring"
                    style={{
                        position: "absolute",
                        inset: -18,
                        border: "1.5px solid rgba(249,115,22,0.55)",
                        borderRadius: "50%",
                        transform: "rotateX(72deg)",
                        boxShadow: "0 0 26px rgba(249,115,22,0.3)",
                    }}
                />
                <div
                    className="orbit-ring orbit-ring-2"
                    style={{
                        position: "absolute",
                        inset: -36,
                        border: "1px dashed rgba(6,182,212,0.55)",
                        borderRadius: "50%",
                        transform: "rotateX(72deg) rotateZ(38deg)",
                    }}
                />

                {/* HUD ticks around the sphere */}
                <svg
                    viewBox="-130 -130 260 260"
                    style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}
                >
                    {Array.from({ length: 60 }).map((_, i) => {
                        const a = (i / 60) * Math.PI * 2;
                        const r1 = 120;
                        const long = i % 5 === 0;
                        const r2 = r1 + (long ? 8 : 4);
                        return (
                            <line
                                key={i}
                                x1={Math.cos(a) * r1}
                                y1={Math.sin(a) * r1}
                                x2={Math.cos(a) * r2}
                                y2={Math.sin(a) * r2}
                                stroke={long ? "rgba(249,115,22,0.55)" : "rgba(148,163,184,0.35)"}
                                strokeWidth={long ? 1.4 : 0.8}
                            />
                        );
                    })}
                </svg>

                {/* Floating data chips */}
                <FloatingChip x={"-2%"} y={"6%"} text="LIVE · 150" color="#f97316" />
                <FloatingChip x={"82%"} y={"22%"} text="54 STATIONS" color="#06b6d4" delay="0.6s" />
                <FloatingChip x={"68%"} y={"86%"} text="θ = 0.34" color="#10b981" delay="1.2s" />
                <FloatingChip x={"-8%"} y={"78%"} text="ROC 0.87" color="#fbbf24" delay="1.8s" />
            </div>
        </div>
    );
}

function FloatingChip({ x, y, text, color, delay = "0s" }) {
    return (
        <div
            className="float-chip"
            style={{
                position: "absolute",
                left: x,
                top: y,
                padding: "5px 10px",
                background: "rgba(10,14,22,0.72)",
                border: `1px solid ${color}`,
                borderRadius: 3,
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                color,
                letterSpacing: "0.1em",
                boxShadow: `0 0 16px ${color}33`,
                backdropFilter: "blur(8px)",
                animationDelay: delay,
                pointerEvents: "none",
            }}
        >
            {text}
        </div>
    );
}
