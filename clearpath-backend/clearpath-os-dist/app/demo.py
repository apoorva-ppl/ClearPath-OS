"""
app/demo.py  —  ClearPath OS control-room demo.

Run:  streamlit run app/demo.py

Tabs:
  1. Command Center  — Live incident feed (from the data) + Simulation mode.
                       In Simulation, set a location + event and the pipeline
                       predicts severity, allocates officers/barricades, draws a
                       diversion, and generates the directive PDF.
  2. After-Action    — predicted vs actual clearance scatter + drift summary.
  3. Model Card      — held-out metrics + feature importance (the "why" slide).

Everything runs in-process: LightGBM models, OR-Tools optimiser, NetworkX
routing. No external services.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# make src importable when run via `streamlit run app/demo.py`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import load_artifacts, plan_incident          # noqa: E402
from src.utils import resolve, load_config                       # noqa: E402

st.set_page_config(page_title="ClearPath OS", layout="wide",
                   initial_sidebar_state="expanded")

CFG = load_config()


@st.cache_resource(show_spinner="Loading models, graph and stations...")
def _artifacts():
    return load_artifacts(CFG)


@st.cache_data
def _incidents():
    df = pd.read_parquet(resolve(CFG["paths"]["features_parquet"]))
    return df


SEV_COLOR = {"High": [220, 40, 40], "Medium": [240, 170, 40], "Low": [70, 170, 90]}


# ============================================================ Command Center ==
def command_center(art):
    st.subheader("Command Center")
    mode = st.radio("Mode", ["Live feed", "Simulation"], horizontal=True)

    df = _incidents()

    if mode == "Live feed":
        st.caption("Recent incidents from the Astram feed. "
                   "Severity is the model's prediction; colour = severity.")
        recent = df.sort_values("start_datetime", ascending=False).head(150).copy()
        # quick predicted severity for display (closure-prob driven)
        import numpy as np
        from src.pipeline import _incident_to_features, _derive_severity
        sevs, cprobs = [], []
        for r in recent.itertuples():
            X = _incident_to_features(
                {"event_cause": r.event_cause, "event_type": r.event_type,
                 "corridor": r.corridor, "lat": r.latitude, "lng": r.longitude,
                 "corridor_recent_count": r.corridor_recent_count,
                 "start_datetime": str(r.start_datetime)}, CFG)
            cprob = float(art["severity"].predict(X)[0])
            dur = max(0.0, float(np.expm1(art["duration"].predict(X)[0])))
            level, _ = _derive_severity(cprob, dur, r.event_cause, CFG)
            sevs.append(level)
            cprobs.append(round(cprob, 2))
        recent["pred_severity"] = sevs
        recent["closure_prob"] = cprobs
        recent["color"] = recent["pred_severity"].map(SEV_COLOR)
        _map(recent.rename(columns={"latitude": "lat", "longitude": "lng"}))
        st.dataframe(
            recent[["id", "event_cause", "corridor", "pred_severity",
                    "closure_prob", "requires_road_closure", "start_datetime"]]
            .reset_index(drop=True), height=260, use_container_width=True)
        return

    # ---- Simulation ----
    st.caption("Drop a hypothetical incident and generate a full response plan.")
    c1, c2, c3 = st.columns(3)
    with c1:
        lat = st.number_input("Latitude", value=12.9716, format="%.4f")
        lng = st.number_input("Longitude", value=77.5946, format="%.4f")
    with c2:
        cause = st.selectbox("Event cause", [
            "accident", "water_logging", "procession", "protest", "vip_movement",
            "public_event", "tree_fall", "vehicle_breakdown", "construction",
            "pot_holes", "congestion", "others"])
        etype = st.selectbox("Type", ["unplanned", "planned"])
    with c3:
        corridor = st.selectbox("Corridor", sorted(df["corridor"].unique().tolist()))
        closure = st.checkbox("Requires road closure", value=True)

    if st.button("Run response plan", type="primary"):
        inc = {"id": "SIM", "lat": lat, "lng": lng, "event_cause": cause,
               "event_type": etype, "corridor": corridor,
               "requires_road_closure": closure}
        with st.spinner("Triage -> routing -> allocation -> directive..."):
            plan = plan_incident(inc, art, with_directive=True)
        _render_plan(plan)


def _render_plan(plan):
    sev = plan["severity"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Predicted severity", sev,
              f"{int(plan['closure']['probability']*100)}% closure risk")
    m2.metric("Est. clearance", plan["duration"]["display"])
    officers = sum(a["officers"] for a in plan["allocation"]["assignments"])
    m3.metric("Officers deployed", officers)
    m4.metric("Barricades", sum(plan["allocation"]["barricades"].values()))

    if plan["supervisor"]["radius_expansions"]:
        st.warning(f"Supervisor expanded the diversion radius "
                   f"{plan['supervisor']['radius_expansions']}x to reach a "
                   f"feasible plan (final {plan['supervisor']['final_radius_m']} m).")

    # map: incident + diversion + baseline
    inc = plan["incident"]
    rows = [{"lat": inc["lat"], "lng": inc["lng"],
             "color": SEV_COLOR[sev], "label": "incident"}]
    _map(pd.DataFrame(rows),
         diversion=plan["diversion"].get("diversion_path"),
         baseline=plan["diversion"].get("baseline_path"))

    st.markdown("**Deployment orders**")
    st.dataframe(pd.DataFrame(plan["allocation"]["assignments"]),
                 use_container_width=True)

    st.markdown("**Official directive**")
    st.code(plan["directive"]["text"], language="text")
    pdf_path = Path(plan["directive"]["pdf_path"])
    if pdf_path.exists():
        st.download_button("Download Official Order (PDF)",
                           pdf_path.read_bytes(), file_name="deployment_directive.pdf",
                           mime="application/pdf")


def _map(points: pd.DataFrame, diversion=None, baseline=None):
    import pydeck as pdk
    layers = []
    if baseline:
        layers.append(pdk.Layer(
            "PathLayer",
            data=[{"path": [[p[1], p[0]] for p in baseline]}],
            get_path="path", get_width=4, get_color=[120, 120, 120],
            width_min_pixels=2))
    if diversion:
        layers.append(pdk.Layer(
            "PathLayer",
            data=[{"path": [[p[1], p[0]] for p in diversion]}],
            get_path="path", get_width=5, get_color=[30, 120, 240],
            width_min_pixels=3))
    layers.append(pdk.Layer(
        "ScatterplotLayer", data=points,
        get_position="[lng, lat]", get_fill_color="color",
        get_radius=120, radius_min_pixels=4, pickable=True))
    view = pdk.ViewState(latitude=float(points["lat"].mean()),
                         longitude=float(points["lng"].mean()), zoom=11)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view,
                             map_style=None,
                             tooltip={"text": "{event_cause}\n{pred_severity}"}))


# =============================================================== After-Action ==
def after_action_tab():
    st.subheader("After-Action Review")
    st.caption("Answers the 'no post-event learning system' gap: compare the "
               "model's predicted clearance time against the ACTUAL time on "
               "closed incidents, and track whether retraining helps.")
    summ_path = resolve("models/after_action.json")
    csv_path = resolve("models/after_action.csv")
    if not summ_path.exists():
        st.info("Run `python -m src.after_action` first.")
        return
    summary = json.loads(summ_path.read_text())
    table = pd.read_csv(csv_path)

    c1, c2, c3 = st.columns(3)
    c1.metric("Closed incidents analysed", summary["n_closed"])
    c2.metric("Seed-model MAE", f"{summary['mae_seed_model_min']} min")
    c3.metric("Matured-model MAE", f"{summary['mae_matured_model_min']} min",
              f"{summary['delta_pct']}%")
    st.info(summary["note"])

    st.markdown("**Predicted vs actual clearance time (held-out incidents)**")
    chart_df = table[["actual_min", "predicted_min"]].copy()
    st.scatter_chart(chart_df, x="actual_min", y="predicted_min", height=360)
    st.dataframe(table.sort_values("abs_error_min", ascending=False).head(20),
                 use_container_width=True)


# ================================================================= Model Card ==
def model_card_tab():
    st.subheader("Model Card")
    st.caption("The classifier predicts a REAL recorded decision "
               "(`requires_road_closure`), not a self-constructed label — so its "
               "AUC reflects genuine forecasting skill. Severity shown elsewhere "
               "is a display rubric layered on these predictions.")

    df = _incidents()
    m_path = resolve(CFG["paths"]["metrics"])
    if m_path.exists():
        metrics = json.loads(m_path.read_text())
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Road-closure classifier (held-out future window)**")
            cl = metrics.get("closure", {})
            a, b = st.columns(2)
            a.metric("ROC-AUC", cl.get("roc_auc"))
            b.metric("PR-AUC", cl.get("pr_auc"))
            a.metric("Closure recall", cl.get("closure_recall"))
            b.metric("Closure precision", cl.get("closure_precision"))
            # class balance (the reviewer's ask): show how rare closures are
            pos = int(df["closure_label"].sum())
            st.caption(f"Class balance: {pos}/{len(df)} incidents required "
                       f"closure ({100*pos/len(df):.1f}%). AUC is reported "
                       f"because accuracy is misleading on a rare positive.")
            if "confusion_matrix" in cl:
                cm = pd.DataFrame(cl["confusion_matrix"],
                                  index=[f"true {l}" for l in cl["labels"]],
                                  columns=[f"pred {l}" for l in cl["labels"]])
                st.dataframe(cm, use_container_width=True)
        with c2:
            st.markdown("**Clearance-duration regressor**")
            dv = metrics.get("duration", {})
            # median-AE first: it's the honest headline (MAE inflated by outliers)
            st.metric("Median abs. error (min)", dv.get("median_ae_minutes"))
            st.metric("Mean abs. error (min)", dv.get("mae_minutes"),
                      help="Inflated by long-tail admin close-outs; the app shows "
                           "a duration tier as the primary output.")
    imp_path = resolve("models/severity_importance.csv")
    if imp_path.exists():
        st.markdown("**Closure-model feature importance (gain)**")
        imp = pd.read_csv(imp_path).set_index("feature")
        st.bar_chart(imp["gain"])


# ======================================================================= main ==
def main():
    st.title("ClearPath OS — Event Congestion Command Center")
    art = _artifacts()
    tab1, tab2, tab3 = st.tabs(["Command Center", "After-Action", "Model Card"])
    with tab1:
        command_center(art)
    with tab2:
        after_action_tab()
    with tab3:
        model_card_tab()


if __name__ == "__main__":
    main()
