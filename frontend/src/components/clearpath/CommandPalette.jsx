import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

const ROUTES = [
    { path: "/", label: "Landing · Intro", hint: "/" },
    { path: "/god-mode", label: "God Mode · Live Map", hint: "⊕" },
    { path: "/sentinel", label: "Citizen Sentinel Grid", hint: "📡" },
    { path: "/intelligence", label: "Intelligence Dashboard", hint: "📊" },
    { path: "/debrief", label: "The Debrief", hint: "🔍" },
];

export default function CommandPalette({ open, onClose }) {
    const [q, setQ] = useState("");
    const [active, setActive] = useState(0);
    const nav = useNavigate();
    const inputRef = useRef(null);

    useEffect(() => {
        if (open) {
            setQ("");
            setActive(0);
            setTimeout(() => inputRef.current?.focus(), 30);
        }
    }, [open]);

    if (!open) return null;
    const items = ROUTES.filter((r) =>
        (r.label + r.path).toLowerCase().includes(q.toLowerCase().trim()),
    );

    const onKey = (e) => {
        if (e.key === "Escape") return onClose();
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => Math.min(items.length - 1, i + 1));
        }
        if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(0, i - 1));
        }
        if (e.key === "Enter") {
            const r = items[active];
            if (r) {
                nav(r.path);
                onClose();
            }
        }
    };

    return (
        <div className="cmdk-overlay" onClick={onClose} data-testid="cmdk">
            <div className="cmdk-box" onClick={(e) => e.stopPropagation()}>
                <input
                    ref={inputRef}
                    value={q}
                    onChange={(e) => {
                        setQ(e.target.value);
                        setActive(0);
                    }}
                    onKeyDown={onKey}
                    placeholder="JUMP TO ROUTE…"
                    data-testid="cmdk-input"
                />
                <div className="cmdk-list">
                    {items.map((r, i) => (
                        <div
                            key={r.path}
                            className={`cmdk-item ${i === active ? "active" : ""}`}
                            onMouseEnter={() => setActive(i)}
                            onClick={() => {
                                nav(r.path);
                                onClose();
                            }}
                            data-testid={`cmdk-item-${r.path.replace("/", "") || "home"}`}
                        >
                            <span>{r.label}</span>
                            <span className="mono" style={{ color: "var(--text-mute)" }}>
                                {r.hint}
                            </span>
                        </div>
                    ))}
                    {items.length === 0 && (
                        <div className="cmdk-item" style={{ color: "var(--text-mute)" }}>
                            No matches.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
