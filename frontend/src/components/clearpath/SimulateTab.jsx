import { useEffect, useMemo, useState } from "react";
import { Circle, CircleMarker, Marker } from "react-leaflet";
import L from "leaflet";
import Panel from "./Panel";
import Badge from "./Badge";
import AnimatedNumber from "./AnimatedNumber";
import AnimatedBar from "./AnimatedBar";
import CityCore from "./CityCore";
import { API } from "@/lib/api";

// ===== Asset catalogue =====
export const ASSET_TYPES = {
  response_hub: {
    key: "response_hub",
    name: "Rapid Response Hub",
    cost: 8_000_000,
    radius_km: 3,
    causes: ["accident", "vehicle_breakdown"],
    effect: "duration_reduction",
    rate_min: 0.1,
    rate_max: 0.5,
    rate_default: 0.3,
    color: "#f97316",
    icon: "H",
    desc: "Reduces incident duration on accidents & breakdowns",
  },
  drainage_grid: {
    key: "drainage_grid",
    name: "Drainage Grid",
    cost: 12_000_000,
    radius_km: 2,
    causes: ["water_logging"],
    effect: "elimination",
    rate_min: 0.5,
    rate_max: 1.0,
    rate_default: 1.0,
    color: "#06b6d4",
    icon: "D",
    desc: "Eliminates water-logging events entirely",
  },
  maintenance_depot: {
    key: "maintenance_depot",
    name: "Maintenance Depot",
    cost: 5_000_000,
    radius_km: 2.5,
    causes: ["pot_holes"],
    effect: "duration_reduction",
    rate_min: 0.1,
    rate_max: 0.5,
    rate_default: 0.15,
    color: "#10b981",
    icon: "M",
    desc: "Cuts pothole-incident repair duration",
  },
};

export const TOTAL_BUDGET = 50_000_000;
export const TOTAL_INCIDENTS = 8057;

// ===== Geometry helpers =====
const R = 6371;
const toRad = (x) => (x * Math.PI) / 180;
export function distKm(a, b) {
  const dLat = toRad(b[0] - a[0]);
  const dLng = toRad(b[1] - a[1]);
  const lat1 = toRad(a[0]);
  const lat2 = toRad(b[0]);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

// Incident counts per asset card (live, from the loaded incidents list)
export function countIncidentsInRange(incidents, lat, lng, radiusKm, causes) {
  if (!incidents) return 0;
  let n = 0;
  for (const i of incidents) {
    if (!causes.includes(i.event_cause)) continue;
    if (distKm([i.lat, i.lng], [lat, lng]) <= radiusKm) n++;
  }
  return n;
}

// ===== Hook: simulate state =====
export function useSimulateState() {
  const [placedAssets, setPlacedAssets] = useState([]);
  const [selectedAssetType, setSelectedAssetType] = useState(null);
  const [reductionRates, setReductionRates] = useState({
    response_hub: ASSET_TYPES.response_hub.rate_default,
    drainage_grid: ASSET_TYPES.drainage_grid.rate_default,
    maintenance_depot: ASSET_TYPES.maintenance_depot.rate_default,
  });
  const [simulationResult, setSimulationResult] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [radarKey, setRadarKey] = useState(0);

  const budgetSpent = placedAssets.reduce(
    (s, a) => s + ASSET_TYPES[a.type].cost,
    0,
  );
  const budget = TOTAL_BUDGET - budgetSpent;

  const placeAsset = (lat, lng) => {
    if (!selectedAssetType) return;
    const cost = ASSET_TYPES[selectedAssetType].cost;
    if (cost > budget) return;
    const id = `A${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    setPlacedAssets((arr) => [
      ...arr,
      {
        id,
        type: selectedAssetType,
        lat,
        lng,
        radius_km: ASSET_TYPES[selectedAssetType].radius_km,
        reduction_rate: reductionRates[selectedAssetType],
      },
    ]);
    setSimulationResult(null);
  };

  const removeAsset = (id) => {
    setPlacedAssets((arr) => arr.filter((a) => a.id !== id));
    setSimulationResult(null);
  };

  const reset = () => {
    setPlacedAssets([]);
    setSelectedAssetType(null);
    setSimulationResult(null);
  };

  const runSimulation = async () => {
    if (placedAssets.length === 0) return;
    setIsSimulating(true);
    setRadarKey((k) => k + 1);
    try {
      const body = {
        assets: placedAssets.map((a) => ({
          type: a.type,
          lat: a.lat,
          lng: a.lng,
          radius_km: a.radius_km,
          reduction_rate: a.reduction_rate,
        })),
      };
      // hold for radar sweep (2s) to play out even on a fast response
      const [resp] = await Promise.all([
        fetch(`${API}/simulate-city`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }).then((r) =>
          r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)),
        ),
        new Promise((r) => setTimeout(r, 2000)),
      ]);
      setSimulationResult(resp);
    } catch (e) {
      // graceful fallback so the UI still demos when backend isn't wired yet
      setSimulationResult({ error: e.message });
    } finally {
      setIsSimulating(false);
    }
  };

  return {
    placedAssets,
    selectedAssetType,
    setSelectedAssetType,
    reductionRates,
    setReductionRates,
    budget,
    simulationResult,
    isSimulating,
    radarKey,
    placeAsset,
    removeAsset,
    reset,
    runSimulation,
  };
}

// SVG iconography for each asset type (replaces single-letter glyphs)
function AssetIcon({ type, color, size = 18 }) {
  const stroke = color;
  if (type === "response_hub") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <path
          d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1v-9z"
          stroke={stroke}
          strokeWidth="1.6"
        />
        <path d="M10 21v-6h4v6" stroke={stroke} strokeWidth="1.6" />
        <circle cx="12" cy="9" r="1.2" fill={stroke} />
      </svg>
    );
  }
  if (type === "drainage_grid") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <path
          d="M12 3c4 5 6 8 6 11a6 6 0 1 1-12 0c0-3 2-6 6-11z"
          stroke={stroke}
          strokeWidth="1.6"
        />
        <path
          d="M9 14c1 1 2 1.5 3 1.5s2-.5 3-1.5"
          stroke={stroke}
          strokeWidth="1.4"
        />
      </svg>
    );
  }
  // maintenance_depot
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M4 18l3-9h10l3 9" stroke={stroke} strokeWidth="1.6" />
      <path d="M2 18h20" stroke={stroke} strokeWidth="1.6" />
      <path d="M8 18v3M16 18v3" stroke={stroke} strokeWidth="1.4" />
      <rect
        x="10"
        y="11"
        width="4"
        height="3"
        stroke={stroke}
        strokeWidth="1.4"
      />
    </svg>
  );
}

// ===== Asset palette (left panel) =====
export function SimulateAssetPalette({ sim, incidents }) {
  const {
    selectedAssetType,
    setSelectedAssetType,
    reductionRates,
    setReductionRates,
    budget,
    placedAssets,
    runSimulation,
    isSimulating,
    simulationResult,
  } = sim;

  const center = [12.9716, 77.5946];

  return (
    <Panel
      title="ASSET PALETTE"
      right={<Badge variant="orange">URBAN ARCHITECT</Badge>}
      testId="asset-palette"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {Object.values(ASSET_TYPES).map((a) => {
          const selected = selectedAssetType === a.key;
          const affordable = budget >= a.cost;
          const rate = reductionRates[a.key];
          const inRange = countIncidentsInRange(
            incidents,
            center[0],
            center[1],
            a.radius_km,
            a.causes,
          );
          return (
            <div
              key={a.key}
              onClick={() =>
                affordable && setSelectedAssetType(selected ? null : a.key)
              }
              data-testid={`asset-card-${a.key}`}
              style={{
                padding: 10,
                borderRadius: 4,
                border: `1.5px solid ${selected ? a.color : "var(--border)"}`,
                background: selected
                  ? `${a.color}14`
                  : "rgba(255,255,255,0.015)",
                cursor: affordable ? "pointer" : "not-allowed",
                opacity: affordable ? 1 : 0.45,
                transition: "all 0.2s",
                boxShadow: selected ? `0 0 18px ${a.color}55` : "none",
              }}
            >
              <div
                style={{ display: "flex", gap: 10, alignItems: "flex-start" }}
              >
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 6,
                    background: `${a.color}22`,
                    border: `1px solid ${a.color}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: a.color,
                    flexShrink: 0,
                    boxShadow: selected
                      ? `0 0 18px ${a.color}88`
                      : `0 0 8px ${a.color}33`,
                    transition: "box-shadow 0.3s",
                  }}
                >
                  <AssetIcon type={a.key} color={a.color} size={20} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    className="display"
                    style={{
                      fontSize: 11,
                      color: a.color,
                      letterSpacing: "0.14em",
                    }}
                  >
                    {a.name}
                  </div>
                  <div
                    className="mono"
                    style={{
                      fontSize: 10,
                      color: "var(--text-dim)",
                      marginTop: 2,
                    }}
                  >
                    ₹{(a.cost / 1_000_000).toFixed(0)}M · {a.radius_km}km
                  </div>
                  <div
                    className="mono"
                    style={{
                      fontSize: 9,
                      color: "var(--text-mute)",
                      marginTop: 4,
                    }}
                  >
                    {a.causes.join(" · ")}
                  </div>
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginTop: 8,
                }}
              >
                <span
                  className="mono"
                  style={{ fontSize: 9, color: "var(--text-mute)" }}
                >
                  IN-RANGE @ CITY CENTER
                </span>
                <span className="mono" style={{ fontSize: 10, color: a.color }}>
                  {inRange.toLocaleString()} incidents
                </span>
              </div>

              {/* reduction slider — only shows for selected */}
              {selected && (
                <div className="fade-in" style={{ marginTop: 10 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: 4,
                    }}
                  >
                    <span
                      className="display"
                      style={{ fontSize: 9, color: "var(--text-dim)" }}
                    >
                      {a.effect === "elimination" ? "ELIMINATION" : "REDUCTION"}{" "}
                      RATE
                    </span>
                    <span
                      className="mono"
                      style={{ fontSize: 10, color: a.color }}
                    >
                      {Math.round(rate * 100)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min={a.rate_min * 100}
                    max={a.rate_max * 100}
                    step={1}
                    value={Math.round(rate * 100)}
                    onChange={(e) =>
                      setReductionRates((r) => ({
                        ...r,
                        [a.key]: Number(e.target.value) / 100,
                      }))
                    }
                    onClick={(e) => e.stopPropagation()}
                    style={{ width: "100%", accentColor: a.color }}
                    data-testid={`rate-${a.key}`}
                  />
                </div>
              )}
            </div>
          );
        })}

        <button
          onClick={runSimulation}
          disabled={placedAssets.length === 0 || isSimulating}
          className="btn"
          style={{
            marginTop: 6,
            width: "100%",
            justifyContent: "center",
            padding: "12px 18px",
            fontSize: 12,
            opacity: placedAssets.length === 0 ? 0.4 : 1,
            cursor: placedAssets.length === 0 ? "not-allowed" : "pointer",
          }}
          data-testid="run-simulation"
        >
          {isSimulating ? (
            <>
              <span className="spin" /> COMPUTING…
            </>
          ) : simulationResult ? (
            "↻ RECALCULATE"
          ) : (
            "⚙ SIMULATE STRUCTURAL IMPACT"
          )}
        </button>

        {simulationResult?.error && (
          <div
            className="fade-in mono"
            style={{
              fontSize: 10,
              color: "var(--amber)",
              padding: 8,
              border: "1px solid var(--amber)",
              borderRadius: 3,
              marginTop: 4,
            }}
          >
            ⚠ Backend not wired yet:{" "}
            <span style={{ color: "var(--text-dim)" }}>
              {simulationResult.error}
            </span>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ===== Budget bar (between tabs and panels) =====
export function SimulateBudgetBar({ sim }) {
  const { budget, reset, placedAssets } = sim;
  const pct = (budget / TOTAL_BUDGET) * 100;
  const color = pct > 60 ? "green" : pct > 25 ? "amber" : "red";

  return (
    <div
      className="panel fade-in"
      style={{
        padding: "8px 14px",
        display: "flex",
        alignItems: "center",
        gap: 14,
        minWidth: 460,
      }}
      data-testid="budget-bar"
    >
      <div style={{ flex: 1 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginBottom: 4,
          }}
        >
          <span
            className="display"
            style={{
              fontSize: 10,
              color: "var(--text-dim)",
              letterSpacing: "0.18em",
            }}
          >
            INFRASTRUCTURE BUDGET
          </span>
          <span
            className="mono"
            style={{ fontSize: 11, color: `var(--${color})` }}
          >
            ₹{budget.toLocaleString("en-IN")} remaining
          </span>
        </div>
        <AnimatedBar value={pct} max={100} color={color} height={6} />
      </div>
      <button
        onClick={reset}
        className="btn ghost"
        disabled={placedAssets.length === 0}
        style={{
          fontSize: 10,
          padding: "6px 12px",
          opacity: placedAssets.length === 0 ? 0.4 : 1,
        }}
        data-testid="reset-assets"
      >
        ✕ RESET
      </button>
    </div>
  );
}

// ===== Map overlays (placed assets + coverage circles + radar sweep) =====
export function SimulatePlacedAssets({ sim }) {
  const { placedAssets } = sim;
  return (
    <>
      {placedAssets.map((a) => {
        const meta = ASSET_TYPES[a.type];
        return (
          <Circle
            key={`circ-${a.id}`}
            center={[a.lat, a.lng]}
            radius={a.radius_km * 1000}
            pathOptions={{
              color: meta.color,
              fillColor: meta.color,
              fillOpacity: 0.08,
              weight: 1.5,
              dashArray: "4 4",
            }}
          />
        );
      })}
      {placedAssets.map((a) => {
        const meta = ASSET_TYPES[a.type];
        const iconSvg =
          a.type === "response_hub"
            ? `<path d='M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1v-9z' stroke='${meta.color}' stroke-width='1.6' fill='none'/><path d='M10 21v-6h4v6' stroke='${meta.color}' stroke-width='1.6' fill='none'/>`
            : a.type === "drainage_grid"
              ? `<path d='M12 3c4 5 6 8 6 11a6 6 0 1 1-12 0c0-3 2-6 6-11z' stroke='${meta.color}' stroke-width='1.6' fill='none'/>`
              : `<path d='M4 18l3-9h10l3 9' stroke='${meta.color}' stroke-width='1.6' fill='none'/><path d='M2 18h20' stroke='${meta.color}' stroke-width='1.6'/>`;
        const ic = L.divIcon({
          className: "asset-pin",
          html: `<div class="asset-pin-inner" style="
            width:36px;height:36px;border-radius:6px;
            background:linear-gradient(135deg, ${meta.color}33, ${meta.color}11);
            border:1.5px solid ${meta.color};
            display:flex;align-items:center;justify-content:center;
            box-shadow:0 0 18px ${meta.color}aa, inset 0 0 8px ${meta.color}44;
          "><svg width="22" height="22" viewBox="0 0 24 24">${iconSvg}</svg></div>`,
          iconSize: [36, 36],
          iconAnchor: [18, 18],
        });
        return (
          <Marker
            key={`pin-${a.id}`}
            position={[a.lat, a.lng]}
            icon={ic}
            eventHandlers={{
              click: () => sim.removeAsset(a.id),
            }}
          />
        );
      })}
    </>
  );
}

// Mark in-range, cause-matching incidents teal AFTER simulation runs.
export function tealIncidentIds(placedAssets, incidents) {
  if (!placedAssets.length || !incidents) return new Set();
  const set = new Set();
  for (const i of incidents) {
    for (const a of placedAssets) {
      const meta = ASSET_TYPES[a.type];
      if (!meta.causes.includes(i.event_cause)) continue;
      if (distKm([i.lat, i.lng], [a.lat, a.lng]) <= a.radius_km) {
        set.add(i.id);
        break;
      }
    }
  }
  return set;
}

// Radar sweep overlay (CSS-only, fired by radarKey)
export function SimulateRadarSweep({ radarKey, active }) {
  if (!active) return null;
  return (
    <div
      key={radarKey}
      aria-hidden
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        zIndex: 400,
        overflow: "hidden",
      }}
      data-testid="radar-sweep"
    >
      <div className="radar-sweep" />
      <div className="radar-ping radar-ping-1" />
      <div className="radar-ping radar-ping-2" />
      <div className="radar-ping radar-ping-3" />
    </div>
  );
}

// ===== City Health Score (right panel) =====
export function SimulateCityHealth({ sim }) {
  const { simulationResult, isSimulating, placedAssets } = sim;

  const hasResult = simulationResult && !simulationResult.error;
  const gr = hasResult
    ? Math.max(0, Math.min(100, simulationResult.gr_score || 0))
    : 0;
  const tier = useMemo(() => {
    if (!hasResult) return { l: "BASELINE", c: "var(--text-mute)" };
    if (gr > 40) return { l: "A", c: "var(--green)" };
    if (gr >= 25) return { l: "B+", c: "var(--cyan)" };
    if (gr >= 10) return { l: "C", c: "var(--amber)" };
    return { l: "D", c: "var(--red)" };
  }, [gr, hasResult]);

  return (
    <Panel
      title="CITY HEALTH SCORE"
      right={<CityCore size={56} label="" />}
      testId="city-health"
    >
      {!hasResult && !isSimulating && (
        <div style={{ textAlign: "center", padding: "20px 4px" }}>
          <ArcGauge value={0} tier="BASELINE" tierColor="var(--text-mute)" />
          <div
            className="display"
            style={{
              fontSize: 12,
              color: "var(--text-dim)",
              letterSpacing: "0.16em",
              marginTop: 8,
            }}
          >
            GRID RESILIENCE: BASELINE — 0%
          </div>
          <div
            className="mono"
            style={{
              fontSize: 11,
              color: "var(--text-mute)",
              marginTop: 10,
              lineHeight: 1.5,
            }}
          >
            Place assets and run simulation.
          </div>
        </div>
      )}

      {isSimulating && (
        <div style={{ textAlign: "center", padding: 30 }}>
          <span className="spin" style={{ width: 22, height: 22 }} />
          <div
            className="display"
            style={{
              fontSize: 11,
              color: "var(--cyan)",
              marginTop: 12,
              letterSpacing: "0.18em",
            }}
          >
            SCANNING {TOTAL_INCIDENTS.toLocaleString()} INCIDENTS…
          </div>
        </div>
      )}

      {hasResult && (
        <div
          className="fade-in"
          style={{ display: "flex", flexDirection: "column", gap: 16 }}
        >
          <div style={{ textAlign: "center" }}>
            <ArcGauge value={gr} tier={tier.l} tierColor={tier.c} />
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 14,
                marginTop: 4,
              }}
            >
              <div
                className="tier-medal"
                style={{ color: tier.c }}
                data-testid={`tier-medal-${tier.l}`}
              >
                <span className="tier-medal-letter" style={{ color: tier.c }}>
                  {tier.l}
                </span>
              </div>
              <div style={{ textAlign: "left" }}>
                <div
                  className="mono"
                  style={{
                    fontSize: 44,
                    lineHeight: 1,
                    color: tier.c,
                    textShadow: `0 0 14px ${tier.c}`,
                  }}
                >
                  <AnimatedNumber value={gr} decimals={1} suffix="%" />
                </div>
                <div
                  className="display"
                  style={{
                    fontSize: 10,
                    color: "var(--text-mute)",
                    letterSpacing: "0.2em",
                    marginTop: 4,
                  }}
                >
                  GRID RESILIENCE
                </div>
              </div>
            </div>
          </div>

          <Section title="RESPONSE BURDEN">
            <RowStat
              l="Historical"
              v={`${Math.round(simulationResult.historical_burden || 0).toLocaleString()} sev-min`}
              color="var(--red)"
            />
            <RowStat
              l="Simulated"
              v={`${Math.round(simulationResult.simulated_burden || 0).toLocaleString()} sev-min`}
              color="var(--green)"
            />
            <RowStat
              l="Reduction"
              v={`${gr.toFixed(1)}%`}
              color="var(--orange)"
              big
            />
          </Section>

          <Section
            title={`INCIDENTS AFFECTED / ${TOTAL_INCIDENTS.toLocaleString()}`}
          >
            {Object.entries(simulationResult.breakdown || {}).map(([k, v]) => (
              <RowStat
                key={k}
                l={ASSET_TYPES[k]?.name || k}
                v={Number(v).toLocaleString()}
                color={ASSET_TYPES[k]?.color || "var(--text-dim)"}
              />
            ))}
            <RowStat
              l="Total"
              v={Number(
                simulationResult.incidents_affected || 0,
              ).toLocaleString()}
              color="var(--cyan)"
              big
            />
          </Section>

          <Section title="ECONOMIC IMPACT / YEAR">
            <RowStat
              l="Hours saved"
              v={`${((simulationResult.economic_value_inr || 0) / 150).toFixed(0)} hr`}
              color="var(--cyan)"
            />
            <RowStat
              l="₹ Value"
              v={`₹${Number(simulationResult.economic_value_inr || 0).toLocaleString("en-IN")}`}
              color="var(--green)"
              big
            />
            <RowStat
              l="Avg duration cut"
              v={`${(simulationResult.avg_duration_reduction_min || 0).toFixed(1)} min`}
              color="var(--amber)"
            />
          </Section>

          <div
            className="mono"
            style={{
              fontSize: 10,
              color: "var(--text-mute)",
              textAlign: "center",
            }}
          >
            {placedAssets.length} asset{placedAssets.length !== 1 ? "s" : ""}{" "}
            placed · scored against {TOTAL_INCIDENTS.toLocaleString()}{" "}
            historical incidents
          </div>
        </div>
      )}
    </Panel>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <div
        className="display"
        style={{
          fontSize: 10,
          color: "var(--text-dim)",
          letterSpacing: "0.18em",
          marginBottom: 8,
          paddingBottom: 6,
          borderBottom: "1px solid var(--border)",
        }}
      >
        {title}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {children}
      </div>
    </div>
  );
}
function RowStat({ l, v, color, big }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "3px 0",
      }}
    >
      <span
        className="mono"
        style={{ fontSize: big ? 11 : 10, color: "var(--text-mute)" }}
      >
        {l}
      </span>
      <span className="mono" style={{ fontSize: big ? 14 : 11, color }}>
        {v}
      </span>
    </div>
  );
}

function ArcGauge({ value, tier, tierColor }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setV(value), 80);
    return () => clearTimeout(t);
  }, [value]);
  const size = 160;
  const r = 64;
  const cx = size / 2;
  const cy = size / 2 + 6;
  const angle = (v / 100) * 180 - 180;
  const polar = (deg) => {
    const rad = (deg * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };
  const arcPath = (a1, a2) => {
    const p1 = polar(a1);
    const p2 = polar(a2);
    const large = a2 - a1 > 180 ? 1 : 0;
    return `M ${p1.x} ${p1.y} A ${r} ${r} 0 ${large} 1 ${p2.x} ${p2.y}`;
  };
  const needle = polar(angle);
  return (
    <svg
      width={size}
      height={size / 2 + 28}
      viewBox={`0 0 ${size} ${size / 2 + 28}`}
    >
      <path
        d={arcPath(-180, 0)}
        fill="none"
        stroke="rgba(148,163,184,0.15)"
        strokeWidth="8"
      />
      <path
        d={arcPath(-180, angle)}
        fill="none"
        stroke={tierColor}
        strokeWidth="8"
        strokeLinecap="round"
        style={{
          filter: `drop-shadow(0 0 8px ${tierColor})`,
          transition: "all 1.2s cubic-bezier(0.16,1,0.3,1)",
        }}
      />
      <line
        x1={cx}
        y1={cy}
        x2={needle.x}
        y2={needle.y}
        stroke={tierColor}
        strokeWidth="2"
        strokeLinecap="round"
        style={{ transition: "all 1.2s cubic-bezier(0.16,1,0.3,1)" }}
      />
      <circle
        cx={cx}
        cy={cy}
        r="5"
        fill="#030712"
        stroke={tierColor}
        strokeWidth="2"
      />
      <text
        x={cx}
        y={size / 2 + 24}
        textAnchor="middle"
        fontFamily="var(--font-display)"
        fontSize="11"
        fill="var(--text-mute)"
        letterSpacing="2"
      >
        {tier}
      </text>
    </svg>
  );
}

// Re-export so GodMode can import everything in one go
export { TealMarkerSentinel };
function TealMarkerSentinel({ ids, incidents }) {
  if (!incidents || !ids?.size) return null;
  return (
    <>
      {incidents
        .filter((i) => ids.has(i.id))
        .map((i) => (
          <CircleMarker
            key={`teal-${i.id}`}
            center={[i.lat, i.lng]}
            radius={5}
            pathOptions={{
              color: "#14b8a6",
              fillColor: "#14b8a6",
              fillOpacity: 0.7,
              weight: 2,
            }}
          />
        ))}
    </>
  );
}
