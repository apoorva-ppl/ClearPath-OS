"""
directive_llm.py  —  Stage 8 (presentation layer).

IN : a structured plan dict from pipeline.py
       {"incident": {...}, "severity": "...", "duration": {...},
        "allocation": {...}, "diversion": {...}}
OUT: - directive text (str)
     - a PDF written to the given path (default models/directive.pdf)

The LLM ONLY formats the already-computed plan into official prose. It performs
no reasoning, optimisation, or routing — those are done deterministically
upstream. This keeps the system trustworthy: the numbers come from the optimiser
and models, the LLM just renders the directive. If no API key is present, a
clean template fallback produces the same document offline.

Run (self-test): python -m src.directive_llm
"""
from __future__ import annotations

import os
from pathlib import Path

from .utils import load_config, resolve, log

SYSTEM = (
    "You are a duty officer drafting an official Police Deployment Directive for "
    "a city traffic control room. Write in crisp, formal, imperative language. "
    "Use ONLY the facts provided in the JSON. Do not invent numbers, names, or "
    "locations. Keep it under 180 words. Structure: a one-line URGENT header, "
    "the situation, the deployment orders (officers/stations/barricades), and the "
    "diversion instruction. No preamble, no sign-off placeholders."
)


def _build_user_prompt(plan: dict) -> str:
    import json
    return ("Draft the directive from this plan:\n```json\n"
            + json.dumps(plan, indent=2, default=str) + "\n```")


def _fallback(plan: dict) -> str:
    inc = plan["incident"]
    alloc = plan["allocation"]
    loc = inc.get("address") or f"{inc['lat']:.4f}, {inc['lng']:.4f}"
    cause = inc.get("event_cause", "incident").replace("_", " ").title()
    lines = [
        f"URGENT DIRECTIVE — {plan['severity'].upper()} IMPACT INCIDENT {inc.get('id','')}",
        "",
        f"SITUATION: {cause} reported at {loc} on corridor "
        f"{inc.get('corridor','N/A')}. "
        f"Estimated clearance: {plan['duration']['display']}.",
        "",
        "DEPLOYMENT ORDERS:",
    ]
    for a in alloc["assignments"]:
        lines.append(f"  - Station {a['station']}: deploy {a['officers']} officer(s) "
                     f"to incident {a['incident_id']} ({a['distance_km']} km).")
    for iid, n in alloc["barricades"].items():
        if n:
            lines.append(f"  - Position {n} barricade(s) at incident {iid}.")
    if alloc.get("uncovered"):
        lines.append(f"  - UNRESOLVED demand at: {', '.join(alloc['uncovered'])} "
                     f"— escalate for additional units.")
    div = plan.get("diversion") or {}
    if div.get("diversion_path"):
        lines += ["", f"DIVERSION: Establish exclusion zone radius "
                  f"{int(div['buffer_radius_m'])} m around incident; "
                  f"redirect through-traffic along the recalculated route. "
                  f"{div.get('affected_edge_count',0)} road segments affected."]
    return "\n".join(lines)


def generate_directive(plan: dict, pdf_path: str | Path = "models/directive.pdf",
                       cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    text = None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=cfg["llm"]["model"],
                max_tokens=cfg["llm"]["max_tokens"],
                system=SYSTEM,
                messages=[{"role": "user", "content": _build_user_prompt(plan)}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            log("directive: generated via Anthropic API")
        except Exception as e:                  # noqa: BLE001
            log(f"directive: API path failed ({e}); using offline template")

    if not text:
        text = _fallback(plan)
        log("directive: generated via offline template")

    pdf_out = resolve(pdf_path)
    _write_pdf(text, pdf_out)
    return {"text": text, "pdf_path": str(pdf_out)}


def _write_pdf(text: str, path: Path) -> None:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "POLICE DEPLOYMENT DIRECTIVE",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.ln(2)
    epw = pdf.w - pdf.l_margin - pdf.r_margin   # effective page width
    for line in text.split("\n"):
        safe = line.encode("latin-1", "replace").decode("latin-1")
        if safe.strip() == "":
            pdf.ln(4)                            # blank spacer line
            continue
        pdf.multi_cell(epw, 6, safe,
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


if __name__ == "__main__":
    demo_plan = {
        "incident": {"id": "FKID000021", "event_cause": "tree_fall",
                     "corridor": "Sankey Road", "lat": 12.9273, "lng": 77.5806,
                     "address": "5th Main Road, Jayanagar"},
        "severity": "High",
        "duration": {"minutes": 142, "display": "~2h 22m (1-4h tier)"},
        "allocation": {
            "assignments": [{"incident_id": "FKID000021", "station": "Sadashivanagar",
                             "officers": 6, "distance_km": 1.2}],
            "barricades": {"FKID000021": 12}, "uncovered": [],
        },
        "diversion": {"buffer_radius_m": 800, "affected_edge_count": 18,
                      "diversion_path": [[12.92, 77.57], [12.93, 77.58]]},
    }
    out = generate_directive(demo_plan)
    print("\n" + out["text"])
    print("\nPDF ->", out["pdf_path"])
