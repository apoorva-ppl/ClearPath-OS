import { useEffect, useRef } from "react";

/**
 * Glassy custom cursor: a large blurry refractive orb that lerps toward the
 * pointer, plus a sharp orange dot at the exact mouse position. Hovering any
 * interactive element grows the orb and shifts its tint. Pure DOM + rAF, no
 * library, no React state churn.
 */
export default function CursorGlow() {
    const orbRef = useRef(null);
    const dotRef = useRef(null);
    const trailRef = useRef(null);
    const stateRef = useRef({
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
        ox: window.innerWidth / 2,
        oy: window.innerHeight / 2,
        tx: window.innerWidth / 2,
        ty: window.innerHeight / 2,
        hover: false,
        down: false,
    });

    useEffect(() => {
        // disable on touch / coarse pointers
        if (window.matchMedia?.("(pointer: coarse)").matches) return;

        document.documentElement.classList.add("cursor-hidden");

        const onMove = (e) => {
            stateRef.current.x = e.clientX;
            stateRef.current.y = e.clientY;
        };
        const onOver = (e) => {
            const t = e.target;
            stateRef.current.hover = !!t.closest?.(
                "a,button,input,textarea,select,[role='button'],.btn,.cmdk-item,.nav-link,canvas,.leaflet-interactive",
            );
        };
        const onDown = () => (stateRef.current.down = true);
        const onUp = () => (stateRef.current.down = false);
        const onLeave = () => {
            if (orbRef.current) orbRef.current.style.opacity = "0";
            if (dotRef.current) dotRef.current.style.opacity = "0";
        };
        const onEnter = () => {
            if (orbRef.current) orbRef.current.style.opacity = "1";
            if (dotRef.current) dotRef.current.style.opacity = "1";
        };

        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseover", onOver);
        window.addEventListener("mousedown", onDown);
        window.addEventListener("mouseup", onUp);
        window.addEventListener("mouseleave", onLeave);
        window.addEventListener("mouseenter", onEnter);

        let raf;
        const tick = () => {
            const s = stateRef.current;
            // orb (slow lerp)
            s.ox += (s.x - s.ox) * 0.16;
            s.oy += (s.y - s.oy) * 0.16;
            // trail (slower lerp for parallax glow)
            s.tx += (s.x - s.tx) * 0.06;
            s.ty += (s.y - s.ty) * 0.06;

            const size = s.hover ? 64 : 36;
            const scale = s.down ? 0.7 : 1;

            if (orbRef.current) {
                orbRef.current.style.transform = `translate3d(${s.ox - size / 2}px, ${s.oy - size / 2}px, 0) scale(${scale})`;
                orbRef.current.style.width = `${size}px`;
                orbRef.current.style.height = `${size}px`;
                orbRef.current.style.borderColor = s.hover ? "rgba(249,115,22,0.7)" : "rgba(148,163,184,0.35)";
                orbRef.current.style.boxShadow = s.hover
                    ? "0 0 26px rgba(249,115,22,0.45), inset 0 0 18px rgba(249,115,22,0.18)"
                    : "0 0 18px rgba(148,163,184,0.18), inset 0 0 14px rgba(148,163,184,0.08)";
            }
            if (dotRef.current) {
                dotRef.current.style.transform = `translate3d(${s.x - 3}px, ${s.y - 3}px, 0)`;
                dotRef.current.style.background = s.hover ? "var(--orange)" : "var(--cyan)";
                dotRef.current.style.boxShadow = s.hover
                    ? "0 0 12px var(--orange)"
                    : "0 0 8px var(--cyan)";
            }
            if (trailRef.current) {
                trailRef.current.style.transform = `translate3d(${s.tx - 140}px, ${s.ty - 140}px, 0)`;
            }
            raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);

        return () => {
            cancelAnimationFrame(raf);
            window.removeEventListener("mousemove", onMove);
            window.removeEventListener("mouseover", onOver);
            window.removeEventListener("mousedown", onDown);
            window.removeEventListener("mouseup", onUp);
            window.removeEventListener("mouseleave", onLeave);
            window.removeEventListener("mouseenter", onEnter);
            document.documentElement.classList.remove("cursor-hidden");
        };
    }, []);

    return (
        <>
            <div ref={trailRef} className="cursor-trail" aria-hidden />
            <div ref={orbRef} className="cursor-orb" aria-hidden />
            <div ref={dotRef} className="cursor-dot" aria-hidden />
        </>
    );
}
