const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
export const API = `${BACKEND_URL}/api`;
export const ASSET_BASE = BACKEND_URL;

export async function getJSON(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json();
}

export async function reverseGeocode(lat, lng) {
  try {
    const res = await fetch(`${API}/geocode?lat=${lat}&lng=${lng}`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    return data.name || "Unknown location";
  } catch {
    return "Unknown location";
  }
}

export function wsURL(path) {
  const base = (BACKEND_URL || window.location.origin).replace(/^http/, "ws");
  return `${base}/api${path}`;
}
