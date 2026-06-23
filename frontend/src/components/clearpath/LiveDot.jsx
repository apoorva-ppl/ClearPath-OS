export default function LiveDot({ variant = "red" }) {
    const cls = variant === "green" ? "green" : variant === "amber" ? "amber" : "";
    return <span className={`live-dot ${cls}`} />;
}
