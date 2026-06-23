<div align="center">

<div align="center">
  <img src="assets/screenshots/landing.webp" width="100%" alt="ClearPath OS" />
  
  <br/>
  <br/>

  <h1>ClearPath OS</h1>
  <p><strong>Enterprise-Grade Municipal Traffic Intelligence Platform</strong></p>
  <p><em>Shifting city infrastructure from volume-based routing to context-aware empathy.</em></p>
</div>

**Enterprise-Grade Municipal Traffic Intelligence Platform**

_Shifting city infrastructure from volume-based routing to context-aware empathy._

---

![Build Status](https://img.shields.io/badge/build-passing-brightgreen?style=flat-square)
![Python](https://img.shields.io/badge/python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)
![Next.js](https://img.shields.io/badge/Next.js-black?style=flat-square&logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![LightGBM](https://img.shields.io/badge/LightGBM-enabled-orange?style=flat-square)
![PostGIS](https://img.shields.io/badge/PostGIS-spatial-336791?style=flat-square&logo=postgresql&logoColor=white)
![Spline](https://img.shields.io/badge/Spline-3D-blueviolet?style=flat-square)

</div>

---

> **"Big disasters are made worse by small traffic jams."**
>
> ClearPath OS is a contextual, machine-learning-driven traffic management operating system built for municipal dispatchers. It ensures emergency responders never get trapped behind low-priority gridlock — by treating every traffic incident not as a volume problem, but as a human one.

---

## Table of Contents

- [Philosophy](#philosophy)
- [Screenshots](#screenshots)
- [Pages and Features](#pages-and-features)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Local Installation](#local-installation)

---

## Philosophy

Standard traffic AI has a fatal flaw: it optimizes for **vehicle volume**. It will clear a highway with 5,000 delayed commuters before a side-street with 50 — but if those 50 cars are blocking the only exit to a burning school, or the entrance to a trauma hospital, the AI's math fails human reality.

**ClearPath OS introduces Geospatial Empathy.**

Before the LightGBM model assigns any severity score, our backend runs a PostGIS spatial radius query. If a minor breakdown occurs within **500 meters** of a Vulnerable Zone — hospital, school, fire station — the system overrides the AI, escalates to `CRITICAL`, and dispatches response before emergency vehicles arrive.

```
INCIDENT DETECTED
      |
      v
 PostGIS Spatial Query (500m radius)
      |
      |-- VULNERABLE ZONE NEARBY? --YES--> [ CRITICAL ] Override
      |                                     Deploy tow response immediately
      |                                     Flag emergency corridor
      |
      +-- NO --> LightGBM Severity Score
                 Standard dispatch queue
```

---

## Screenshots

### Landing Page

![Landing Page](assets/screenshots/landing.webp)

### God Mode — Live Map

![God Mode Live Map](assets/screenshots/live_mode.webp)

### God Mode — Simulate

![God Mode Simulate](assets/screenshots/simulate.webp)

### God Mode — Stress Test

![God Mode Stress Test](assets/screenshots/stress.webp)

### Sentinel — Complaint Forum

![Sentinel](assets/screenshots/sentinel.webp)

### Intelligence Page

![Intelligence](assets/screenshots/intelligence.webp)

### Debrief Page

![Debrief](assets/screenshots/debrief.webp)

### Vulnerable Zone Mode

![Vulnerable Zones](assets/screenshots/vulnerable.webp)

---

## Pages and Features

### 1. Landing Page

The command entry point for Bengaluru Traffic Police dispatchers.

- Spline-rendered 3D globe visualizing the city as a live operational orb, with real-time telemetry annotations (`LIVE: 150`, `ROC: 0.87`, `54 STATIONS`)
- Bold typographic hero — INCIDENT. ROUTE. RESPOND. — communicates the three-step dispatch logic at a glance
- Live system status bar showing active incidents and WebSocket connection state
- Direct CTAs routing dispatchers to God Mode or the Intelligence dashboard
- Navigation links to all six platform modules

![Landing Page](assets/screenshots/landing.webp)

---

### 2. God Mode — Simulation Engine

The civic planning and operational control surface. Three distinct modes on one map.

#### Live Map

Real-time ingestion of city traffic telemetry streamed over WebSocket.

- Full Bengaluru map with color-coded incident markers: HIGH (red), MEDIUM (amber), LOW (green)
- Police station availability markers (blue = full, amber = low stock)
- Baseline blocked routes and active diversion overlays
- Agent activity panel: TRIAGE, SPATIAL, LOGISTICS, SUPERVISOR, DIRECTIVE, COMPLETE — with live status updates
- Station Status panel listing all 54 stations and unit counts
- Live feed sidebar showing incident IDs, types, and corridor tags in real time

![God Mode Live](assets/screenshots/live_mode.webp)

#### Simulate — Urban Architect Mode

Lets civic planners place infrastructure assets and model their impact before committing budget.

- Asset palette: Rapid Response Hub (Rs. 8M, 3km radius), Drainage Grid (Rs. 12M, 2km), Maintenance Depot (Rs. 5M, 2.5km)
- Drag-and-drop asset placement directly on the city map
- Real-time infrastructure budget counter (Rs. 1,30,00,000 remaining)
- Per-asset elimination rate slider and incident-in-range counter
- Holographic skyline visualization rendering placed assets as 3D columns
- City Health Score computed as assets are placed

![God Mode Simulate](assets/screenshots/simulate.webp)

#### Stress Test

Push the ML model to failure by simulating cascading multi-ward gridlocks.

- COUNT slider to inject 1–10 simultaneous high-severity incidents
- Severity toggle: LOW / MIXED / HIGH
- RUN STRESS LOOP button triggers multi-agent response pipeline
- Crisis Comms panel: auto-generates Tweet, SMS, and Audio dispatch for each active incident
- Plan Output cards: per-incident closure probability, officer count, barricades required
- Agent pipeline tracks TRIAGE through COMPLETE with live status on each stage

![God Mode Stress Test](assets/screenshots/stress.webp)

---

### 3. Sentinel — Complaint Forum

Crowdsourced telemetry pipeline for hyper-local anomalies that sensors miss. Bilingual: English and Kannada.

- File a complaint in EN or KN — the language toggle switches the entire input context
- Complaint type selector: MISSED CLOSURE, WRONG DURATION, WRONG SEVERITY, SOMETHING ELSE
- Free-text description field (800 character limit) with character counter
- Every complaint is hashed, anonymised, and routed to the model retraining queue — no PII stored
- Live Complaint Grid: a Bengaluru map showing complaint density in real time
- Swarm Detection panel: auto-triggers a dispatch alert when 3 or more complaints cluster within ~500m in a 5-minute window
- Scan interval: 10 seconds
- Recent submissions feed showing verified and pending reports

![Sentinel](assets/screenshots/sentinel.webp)

---

### 4. Intelligence Page — The Control Room

Palantir-style high-density telemetry dashboard. The operational heart of ClearPath OS.

**Closure Model panel**

- ROC-AUC: 0.784
- PR-AUC: 0.312
- Recall (Closure): 0.626
- Precision (Closure): 0.228
- Confusion matrix: TN 1,835 / FP 488 / FN 86 / TP 144
- Threshold tuned for recall at theta = 0.500

**Duration Regressor panel**

- Median AE: 30.9 min
- MAE: 101.9m
- Train / Val split: 1692 / 764

**Live Incident Feed**

- Streaming incident IDs with cause, corridor, heat score, and age
- HIGH severity incidents flagged in red, LOW in green

**Cause Breakdown**

- VEHICLE_BREAKDOWN 54%, POT_HOLES 18%, WATER_LOGGING 8%, TREE_FALL 8%, OTHERS 4%...

**Hourly Heatmap (24H)**

- Colour-coded hour blocks showing incident density across the day

**Corridor Risk — Top 10**

- Ranked corridors by active incident count: NON-CORRIDOR 63, ORR EAST 1: 13, BELLARY ROAD 1: 11...

![Intelligence](assets/screenshots/intelligence.webp)

---

### 5. Debrief Page — Model Accountability

We don't hide the algorithm's mistakes. We surface every single one.

> **"THE MODEL MADE MISTAKES. HERE IS EVERY ONE OF THEM."**

- Predicted vs Actual scatter plot (200 data points) with error-coloured dots: green < 20m, amber 20-60m, red > 60m
- Hover any point to see the raw incident ID, actual duration, predicted duration, and error magnitude
- Summary metrics: Total Incidents 500, Median AE 29.9m, Mean Actual 118.6m, Mean Predicted 53.9m
- Drift Note: auto-generated plain-language explanation of where the model is systematically failing
- "What This Means" section: contextual analysis for ML engineers on retraining triggers
- Anomaly Detection: 23 anomalies detected, with progress bar showing detection coverage
- Drift Gauge visualization showing current model drift severity

![Debrief](assets/screenshots/debrief.webp)

---

### 6. Vulnerable Zone Mode

This page is not a dashboard. It is a statement.

> _"Right now, 2 ambulance routes and 2 school zones in Bengaluru are blocked."_
> _"Standard traffic AI counts cars on the road. ClearPath OS asks who is inside them."_

- Live counter of blocked Hospital Corridors, School Zones, and Fire Corridors at the top of the page
- Filter tabs: ALL, HOSPITAL, SCHOOL, FIRE — each showing count of active blockages
- Each incident card displays: zone name and distance, incident type, neighbourhood, full human-readable impact description, severity badge (CRITICAL / ELEVATED), and time since report
- Right panel: selected incident detail with closure probability and estimated duration
- Incident types surface real civic impact — not just road data. A tree fall near a school during pickup hours. Pot holes blocking an ambulance corridor. The system names who is affected.
- Emotional design intent: warm amber and red tones, large typography, no technical jargon in the descriptions — built for a dispatcher making a human call in under 10 seconds

![Vulnerable Zones](assets/screenshots/vulnerable.webp)

---

## Project Structure

```
clearpath-os/
|
+-- frontend/
|   +-- app/
|   |   +-- page.tsx                  # Landing page
|   |   +-- god-mode/
|   |   |   +-- page.tsx              # God Mode container
|   |   |   +-- components/
|   |   |       +-- LiveMap.tsx       # Live map + agent panel
|   |   |       +-- Simulate.tsx      # Urban architect mode
|   |   |       +-- StressTest.tsx    # Stress test + crisis comms
|   |   +-- sentinel/
|   |   |   +-- page.tsx              # Complaint forum (bilingual)
|   |   +-- intelligence/
|   |   |   +-- page.tsx              # Control room dashboard
|   |   +-- debrief/
|   |   |   +-- page.tsx              # Model accountability
|   |   +-- vulnerable/
|   |       +-- page.tsx              # Vulnerable zone alerts
|   +-- components/
|   |   +-- ui/                       # Shared UI primitives
|   |   +-- SplineGlobe.tsx           # Spline 3D scene (landing)
|   |   +-- IncidentMap.tsx           # Shared map component
|   |   +-- AgentPanel.tsx            # Multi-agent activity sidebar
|   |   +-- LiveFeed.tsx              # Streaming incident feed
|   +-- lib/
|   |   +-- websocket.ts              # WS connection manager
|   |   +-- api.ts                    # API client
|   +-- public/
|   |   +-- spline/                   # Spline scene exports
|   +-- package.json
|   +-- tailwind.config.ts
|
+-- backend/
|   +-- main.py                       # FastAPI entry point
|   +-- routers/
|   |   +-- incidents.py              # Incident CRUD + severity
|   |   +-- geospatial.py             # PostGIS radius queries
|   |   +-- sentinel.py               # Complaint ingestion
|   |   +-- stress.py                 # Stress test simulation
|   +-- ml/
|   |   +-- model.py                  # LightGBM inference
|   |   +-- train.py                  # Training pipeline
|   |   +-- debrief.py                # Drift detection
|   +-- db/
|   |   +-- schema.sql                # PostgreSQL + PostGIS schema
|   |   +-- seed.py                   # Sample data seeder
|   +-- requirements.txt
|
+-- assets/
|   +-- screenshots/
|       +-- landing.png
|       +-- god_mode_live.png
|       +-- god_mode_simulate.png
|       +-- god_mode_stress.png
|       +-- sentinel.png
|       +-- intelligence.png
|       +-- debrief.png
|       +-- vulnerable.png
|
+-- .env.example
+-- README.md
```

---

## Tech Stack

### Frontend

| Technology            | Usage                                             |
| --------------------- | ------------------------------------------------- |
| React 18 / Next.js 14 | Component architecture, app router                |
| Tailwind CSS          | Utility-first styling, semantic color grading     |
| Spline                | 3D globe scene on landing page                    |
| Recharts / D3.js      | Intelligence page charts, scatter plots, heatmaps |
| Mapbox GL / Leaflet   | Live incident map in God Mode                     |
| WebSocket (native)    | Real-time incident feed and agent activity        |

### Backend and ML Pipeline

| Technology            | Usage                                                     |
| --------------------- | --------------------------------------------------------- |
| Python 3.9+ / FastAPI | High-concurrency API, WebSocket server                    |
| LightGBM              | Incident closure classification                           |
| XGBoost               | Incident duration regression                              |
| PostgreSQL + PostGIS  | Geospatial radius queries, 500m Vulnerable Zone detection |
| Pandas / Scikit-learn | Feature engineering, model evaluation                     |

---

## Local Installation

### Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL with PostGIS extension enabled

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/clearpath-os.git
cd clearpath-os

# 2. Backend — create virtual environment
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env: set DATABASE_URL, PostGIS credentials, model path

# 4. Start the FastAPI server
uvicorn main:app --reload
# Runs at http://localhost:8000

# 5. Frontend — open a new terminal
cd ../frontend
npm install
npm run dev
# Runs at http://localhost:3000
```

### Environment Variables

```env
DATABASE_URL=postgresql://user:password@localhost:5432/clearpath
POSTGIS_ENABLED=true
VULNERABLE_ZONE_RADIUS_METERS=500
MODEL_PATH=./ml/models/lightgbm_closure.pkl
REGRESSOR_PATH=./ml/models/xgb_duration.pkl
WEBSOCKET_PORT=8001
```

---

<div align="center">

**ClearPath OS** — built for Bengaluru Traffic Police

_Standard traffic AI counts cars on the road. ClearPath OS asks who is inside them._

</div>
