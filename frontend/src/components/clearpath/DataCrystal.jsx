import { useEffect, useRef, useState } from "react";

/**
 * Small interactive "Spline-like" 3D widget — pure CSS/SVG, no Three / Spline runtime.
 *
 * - A glowing core inside a rotating octahedron wireframe.
 * - Continuously rotates on Y; hover speeds it up and the core brightens.
 * - Cursor proximity tilts the rig (parallax).
 * - Click = pulse burst.
 *
 * Designed to be dropped in a corner of any page (size 80-140px).
 */
export default function DataCrystal({
    size = 110,
    color = "var(--orange)",
    label = "CORE",
    showLabel = true,
    onClick,
    testId,
}) {
    const wrapRef = useRef(null);
    const rigRef = useRef(null);
    const [pulse, setPulse] = useState(0);

    useEffect(() => {
        const wrap = wrapRef.current;
        const rig = rigRef.current;
        if (!wrap || !rig) return;
        const onMove = (e) => {
            const r = wrap.getBoundingClientRect();
            // proximity falloff so distant cursor doesn't drag the rig
            const cx = r.left + r.width / 2;
            const cy = r.top + r.height / 2;
            const dx = (e.clientX - cx) / 280;
            const dy = (e.clientY - cy) / 280;
            const clamp = (v) => Math.max(-1, Math.min(1, v));
            rig.style.setProperty("--tilt-x", `${clamp(-dy) * 18}deg`);
            rig.style.setProperty("--tilt-y", `${clamp(dx) * 18}deg`);
        };
        window.addEventListener("mousemove", onMove);
        return () => window.removeEventListener("mousemove", onMove);
    }, []);

    const handleClick = () => {
        setPulse((p) => p + 1);
        onClick?.();
    };

    return (
        <button
            ref={wrapRef}
            onClick={handleClick}
            data-testid={testId || "data-crystal"}
            aria-label={label}
            style={{
                width: size,
                height: size,
                border: "none",
                background: "transparent",
                padding: 0,
                cursor: "pointer",
                position: "relative",
                perspective: 900,
                "--core-color": color,
            }}
            className="data-crystal"
        >
            {/* halo */}
            <span
                style={{
                    position: "absolute",
                    inset: -10,
                    borderRadius: "50%",
                    background: `radial-gradient(circle, ${color}33 0%, transparent 65%)`,
                    filter: "blur(8px)",
                    pointerEvents: "none",
                }}
            />
            <span
                ref={rigRef}
                className="dc-rig"
                style={{
                    width: "100%",
                    height: "100%",
                    display: "block",
                    transformStyle: "preserve-3d",
                    transition: "transform 0.4s cubic-bezier(0.16,1,0.3,1)",
                }}
            >
                <svg
                    viewBox="-60 -60 120 120"
                    style={{
                        position: "absolute",
                        inset: 0,
                        width: "100%",
                        height: "100%",
                        overflow: "visible",
                    }}
                >
                    <defs>
                        <radialGradient id="dc-core">
                            <stop offset="0%" stopColor="#fff" />
                            <stop offset="35%" stopColor={color} />
                            <stop offset="100%" stopColor="rgba(0,0,0,0)" />
                        </radialGradient>
                    </defs>
                    {/* glowing core */}
                    <circle cx="0" cy="0" r="14" fill="url(#dc-core)" className="dc-core" />

                    {/* octahedron wireframe: 6 vertices */}
                    <g className="dc-spin">
                        {/* top/bottom + 4 around */}
                        <g stroke={color} strokeWidth="1" fill="none" opacity="0.85">
                            <polygon points="0,-44 36,0 0,44 -36,0" />
                            <line x1="0" y1="-44" x2="0" y2="44" />
                            <line x1="-36" y1="0" x2="36" y2="0" />
                            {/* faux 3D faces with offset */}
                            <polygon
                                points="0,-44 28,-16 0,44 -28,-16"
                                stroke="rgba(6,182,212,0.7)"
                                strokeWidth="0.8"
                                opacity="0.7"
                            />
                            <polygon
                                points="0,-44 -28,-16 0,44 28,-16"
                                stroke="rgba(6,182,212,0.4)"
                                strokeWidth="0.6"
                                opacity="0.55"
                            />
                        </g>
                        {/* corner nodes */}
                        {[
                            [0, -44],
                            [36, 0],
                            [0, 44],
                            [-36, 0],
                            [28, -16],
                            [-28, -16],
                        ].map(([x, y], i) => (
                            <circle
                                key={i}
                                cx={x}
                                cy={y}
                                r="1.8"
                                fill="#fbbf24"
                                style={{ filter: "drop-shadow(0 0 4px #fbbf24)" }}
                            />
                        ))}
                    </g>

                    {/* counter-spinning outer dashed ring */}
                    <g className="dc-spin-rev">
                        <circle
                            cx="0"
                            cy="0"
                            r="52"
                            fill="none"
                            stroke={color}
                            strokeWidth="0.7"
                            strokeDasharray="2 4"
                            opacity="0.6"
                        />
                    </g>

                    {/* click pulse */}
                    {Array.from({ length: 2 }).map((_, i) => (
                        <circle
                            key={`${pulse}-${i}`}
                            cx="0"
                            cy="0"
                            r="20"
                            fill="none"
                            stroke={color}
                            strokeWidth="1.5"
                            className="dc-burst"
                            style={{ animationDelay: `${i * 0.15}s` }}
                        />
                    ))}
                </svg>
            </span>
            <span
                style={{
                    display: showLabel ? "block" : "none",
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
        </button>
    );
}
