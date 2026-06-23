import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import LiveDot from "./LiveDot";
import DataCrystal from "./DataCrystal";

const LINKS = [
  { to: "/god-mode", label: "GOD MODE", icon: "⊕" },
  { to: "/sentinel", label: "ISSUE TRACKER", icon: "⚑" },
  { to: "/intelligence", label: "INTELLIGENCE", icon: "⧉" },
  { to: "/debrief", label: "DEBRIEF", icon: "⌖" },
  { to: "/vulnerable", label: "VULNERABLE ZONES", icon: "⚠" },
];

function useIstClock() {
  const [s, setS] = useState("");
  useEffect(() => {
    const tick = () => {
      const d = new Date();
      const fmt = d.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour12: false,
      });
      setS(fmt + " IST");
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return s;
}

export default function NavBar({ onCmd }) {
  const clock = useIstClock();
  return (
    <header className="nav-shell" data-testid="navbar">
      <div className="nav-inner">
        <NavLink to="/" className="nav-brand" data-testid="nav-brand">
          CLEARPATH OS
        </NavLink>
        {LINKS.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            data-testid={`nav-link-${l.to.slice(1)}`}
          >
            <span style={{ marginRight: 6, opacity: 0.7 }}>{l.icon}</span>
            {l.label}
          </NavLink>
        ))}
        <div className="nav-right">
          <DataCrystal
            size={36}
            label="CORE"
            showLabel={false}
            testId="nav-crystal"
          />
          <button
            className="btn ghost"
            onClick={onCmd}
            data-testid="cmd-trigger"
            style={{ fontSize: 10 }}
            title="Open command palette (⌘K)"
          >
            ⌘K
          </button>
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <LiveDot variant="green" />
            <span className="mono">{clock}</span>
          </span>
        </div>
      </div>
    </header>
  );
}
