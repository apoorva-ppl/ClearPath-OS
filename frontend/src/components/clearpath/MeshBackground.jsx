import { useEffect, useRef } from "react";

/**
 * Canvas-based animated gradient mesh. Several large soft blobs orbit slowly
 * on a dark canvas; the result is a slow-flowing "Spline-ish" aurora.
 */
export default function MeshBackground({ height = "100vh" }) {
    const ref = useRef(null);

    useEffect(() => {
        const c = ref.current;
        if (!c) return;
        const ctx = c.getContext("2d");
        let raf;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);

        const resize = () => {
            c.width = c.clientWidth * dpr;
            c.height = c.clientHeight * dpr;
        };
        resize();
        window.addEventListener("resize", resize);

        const blobs = [
            { col: "rgba(249,115,22,0.55)", r: 380, x: 0.2, y: 0.3, sx: 0.00009, sy: 0.00007 },
            { col: "rgba(6,182,212,0.45)", r: 360, x: 0.75, y: 0.7, sx: 0.00011, sy: -0.00006 },
            { col: "rgba(16,185,129,0.32)", r: 300, x: 0.5, y: 0.85, sx: -0.00008, sy: 0.00009 },
            { col: "rgba(245,158,11,0.32)", r: 280, x: 0.85, y: 0.2, sx: -0.00010, sy: -0.00007 },
            { col: "rgba(59,130,246,0.32)", r: 320, x: 0.1, y: 0.8, sx: 0.00008, sy: -0.00009 },
        ];

        const start = performance.now();
        const draw = (t) => {
            const elapsed = t - start;
            const W = c.width;
            const H = c.height;
            ctx.clearRect(0, 0, W, H);
            ctx.fillStyle = "#030712";
            ctx.fillRect(0, 0, W, H);

            ctx.globalCompositeOperation = "screen";
            blobs.forEach((b) => {
                const cx = (b.x + Math.sin(elapsed * b.sx) * 0.18) * W;
                const cy = (b.y + Math.cos(elapsed * b.sy) * 0.18) * H;
                const r = b.r * dpr;
                const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
                g.addColorStop(0, b.col);
                g.addColorStop(1, "rgba(0,0,0,0)");
                ctx.fillStyle = g;
                ctx.beginPath();
                ctx.arc(cx, cy, r, 0, Math.PI * 2);
                ctx.fill();
            });
            ctx.globalCompositeOperation = "source-over";

            // grain
            ctx.fillStyle = "rgba(255,255,255,0.018)";
            for (let i = 0; i < 12; i++) {
                ctx.fillRect(Math.random() * W, Math.random() * H, 1, 1);
            }

            raf = requestAnimationFrame(draw);
        };
        raf = requestAnimationFrame(draw);

        return () => {
            cancelAnimationFrame(raf);
            window.removeEventListener("resize", resize);
        };
    }, []);

    return (
        <canvas
            ref={ref}
            style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height,
                zIndex: 0,
                pointerEvents: "none",
                filter: "blur(36px) saturate(140%)",
                opacity: 0.85,
            }}
        />
    );
}
