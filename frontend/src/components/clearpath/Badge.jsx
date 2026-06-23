export default function Badge({ children, variant = "info", className = "" }) {
    return (
        <span className={`badge ${variant} ${className}`} data-testid={`badge-${variant}`}>
            {children}
        </span>
    );
}

export function severityVariant(s) {
    const v = String(s || "").toLowerCase();
    if (v.startsWith("high") || v === "h") return "high";
    if (v.startsWith("med") || v === "m") return "medium";
    if (v.startsWith("low") || v === "l") return "low";
    return "info";
}
