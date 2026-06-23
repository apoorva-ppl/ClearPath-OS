import AnimatedNumber from "./AnimatedNumber";

export default function StatCard({ label, value, sub, decimals = 0, suffix = "", testId }) {
    return (
        <div className="stat-card" data-testid={testId}>
            <div className="label">{label}</div>
            <div className="value">
                <AnimatedNumber value={value} decimals={decimals} suffix={suffix} />
            </div>
            {sub && <div className="sub">{sub}</div>}
        </div>
    );
}
