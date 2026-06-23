import { useEffect, useState } from "react";

export default function AnimatedBar({
    value,
    max = 100,
    color = "orange",
    label,
    valueLabel,
    height = 6,
    delay = 0,
}) {
    const [w, setW] = useState(0);
    useEffect(() => {
        const t = setTimeout(() => {
            const pct = Math.max(0, Math.min(100, (value / max) * 100));
            setW(pct);
        }, delay + 40);
        return () => clearTimeout(t);
    }, [value, max, delay]);

    return (
        <div className="w-full" data-testid={`abar-${label || "bar"}`}>
            {(label || valueLabel) && (
                <div className="flex justify-between items-center mb-1.5">
                    {label && (
                        <span
                            className="display"
                            style={{
                                fontSize: 10,
                                color: "var(--text-dim)",
                                letterSpacing: "0.14em",
                            }}
                        >
                            {label}
                        </span>
                    )}
                    {valueLabel && (
                        <span
                            className="mono"
                            style={{ fontSize: 11, color: "var(--text)" }}
                        >
                            {valueLabel}
                        </span>
                    )}
                </div>
            )}
            <div className="abar" style={{ height }}>
                <div className={`abar-fill ${color}`} style={{ width: `${w}%` }} />
            </div>
        </div>
    );
}
