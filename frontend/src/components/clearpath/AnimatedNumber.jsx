import { useEffect, useRef, useState } from "react";

export default function AnimatedNumber({
    value,
    duration = 900,
    decimals = 0,
    suffix = "",
    prefix = "",
    className = "",
}) {
    const [display, setDisplay] = useState(0);
    const fromRef = useRef(0);
    const startRef = useRef(null);
    const rafRef = useRef(null);

    useEffect(() => {
        const target = Number(value) || 0;
        const from = fromRef.current;
        startRef.current = null;
        const ease = (t) => 1 - Math.pow(1 - t, 3);

        const step = (ts) => {
            if (!startRef.current) startRef.current = ts;
            const p = Math.min((ts - startRef.current) / duration, 1);
            const v = from + (target - from) * ease(p);
            setDisplay(v);
            if (p < 1) rafRef.current = requestAnimationFrame(step);
            else fromRef.current = target;
        };
        rafRef.current = requestAnimationFrame(step);
        return () => cancelAnimationFrame(rafRef.current);
    }, [value, duration]);

    const formatted =
        decimals > 0
            ? display.toFixed(decimals)
            : Math.round(display).toLocaleString();
    return (
        <span className={`mono ${className}`}>
            {prefix}
            {formatted}
            {suffix}
        </span>
    );
}
