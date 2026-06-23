<div align="center">

```
 ██████╗██╗     ███████╗ █████╗ ██████╗ ██████╗  █████╗ ████████╗██╗  ██╗     ██████╗ ███████╗
██╔════╝██║     ██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██║  ██║    ██╔═══██╗██╔════╝
██║     ██║     █████╗  ███████║██████╔╝██████╔╝███████║   ██║   ███████║    ██║   ██║███████╗
██║     ██║     ██╔══╝  ██╔══██║██╔══██╗██╔═══╝ ██╔══██║   ██║   ██╔══██║    ██║   ██║╚════██║
╚██████╗███████╗███████╗██║  ██║██║  ██║██║     ██║  ██║   ██║   ██║  ██║    ╚██████╔╝███████║
 ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝     ╚═════╝ ╚══════╝
```

**Enterprise-Grade Municipal Traffic Intelligence Platform**

_Shifting city infrastructure from volume-based routing to context-aware empathy._

---

![Build Status](https://img.shields.io/badge/build-passing-brightgreen?style=flat-square)
![Python](https://img.shields.io/badge/python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![LightGBM](https://img.shields.io/badge/LightGBM-enabled-orange?style=flat-square)
![PostGIS](https://img.shields.io/badge/PostGIS-spatial-336791?style=flat-square&logo=postgresql&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)

</div>

---

> **"Big disasters are made worse by small traffic jams."**
>
> ClearPath OS is a contextual, machine-learning-driven traffic management operating system built for municipal dispatchers. It ensures emergency responders never get trapped behind low-priority gridlock — by treating every traffic incident not as a volume problem, but as a human one.

---

## 📖 Table of Contents

- [The Core Philosophy](#-the-core-philosophy--geospatial-empathy)
- [Live System Overview](#-live-system-overview)
- [Platform Modules](#-platform-modules)
- [Technical Stack](#-technical-stack)
- [Local Installation](#-local-installation)
- [Model Accountability](#-model-accountability--the-debrief-protocol)
- [Team](#-team)

---

## 🌍 The Core Philosophy — Geospatial Empathy

Standard traffic AI has a fatal flaw: it optimizes for **vehicle volume**. It will prioritize clearing a highway with 5,000 delayed commuters over a side-street with 50 delayed cars.

But if those 50 cars are blocking the only exit to a burning school — or the entrance to a trauma hospital — the AI's math fails human reality.

### The Override Protocol

```
INCIDENT DETECTED
      │
      ▼
┌─────────────────────────────────────────┐
│  PostGIS Spatial Radius Query (500m)    │
│  Checking proximity to Vulnerable Zones │
└─────────────────────────────────────────┘
      │
      ├── VULNERABLE ZONE NEARBY? ──YES──▶  [ CRITICAL ] Override
      │                                      Deploy tow response NOW
      │                                      Flag emergency corridor
      │
      └── NO ──▶  LightGBM Severity Score
                  Standard dispatch queue
```

Before the ML model assigns any severity score, our backend executes a rapid **PostGIS spatial radius query**. If a minor breakdown occurs within **500 meters** of a Vulnerable Zone (Hospitals, High-Density Coaching Hubs, Fire Stations), the system mathematically overrides the AI — elevating the incident to `[ CRITICAL ]` and dispatching response _before_ emergency vehicles arrive.

---

## 🚦 Live System Overview

| Metric                     | Value                               |
| -------------------------- | ----------------------------------- |
| Model Confidence (ROC-AUC) | `94.2%`                             |
| Duration Prediction MAE    | `± 3.4 min`                         |
| Vulnerable Zone Radius     | `500 m`                             |
| Incident Severity Tiers    | `CRITICAL / ELEVATED / MONITOR`     |
| Data Ingestion             | Real-time + Crowdsourced (Sentinel) |

---

## ⚙️ Platform Modules

### `MODULE_01` — Command Entry _(Landing & Executive Overview)_

The entry point of ClearPath OS. A high-performance interface providing a macroscopic view of city health, active municipal alerts, and system status. Designed for rapid situational awareness at a glance.

---

### `MODULE_02` — Mission Briefing _(Intro Video)_

A 2-minute architectural breakdown and mission statement detailing how ClearPath OS intercepts data and transforms it into actionable municipal dispatches.

---

### `MODULE_03` — God Mode 🔴 _(The Simulation Engine)_

Designed for civic planners. God Mode allows users to manipulate the city's traffic matrix in real-time.

| Feature         | Description                                                                   |
| --------------- | ----------------------------------------------------------------------------- |
| **Live Map**    | Real-time ingestion of active city telemetry and vehicle flow                 |
| **Simulate**    | Inject hypothetical bottlenecks (e.g., _"Tree Fall on Outer Ring Road"_)      |
| **Stress Test** | Simulate cascading multi-ward gridlocks to find municipal response thresholds |

---

### `MODULE_04` — Sentinel 🟢 _(Crowdsourced Telemetry)_

A crowdsourced telemetry ingestion pipeline. Citizens report hyper-local anomalies — water-logging, broken-down trucks — that traditional sensors miss entirely. The system cross-verifies reports against live model predictions to filter noise.

```
Citizen Report ──▶ Sentinel Ingestion ──▶ Cross-verify vs. LightGBM ──▶ Validate / Discard
```

---

### `MODULE_05` — Intelligence 🔵 _(The Control Room)_

The operational heart of the platform. A Palantir-style, high-density telemetry dashboard built for human dispatchers.

- Live **LightGBM inference streams** and active corridor predictions
- Dynamic **severity badging** with color-coded priority tiers
- Real-time **precision/recall metrics** (ROC-AUC) — dispatchers always know the AI's exact confidence level

---

### `MODULE_06` — Vulnerable Zone 🔴 _(Contextual Override)_

The real-world implementation of the Geospatial Empathy engine. When an incident threatens a high-risk civic asset, this module activates high-contrast alert tags:

```
[ 🎒 SCHOOL ZONE: ACTIVE ]     ←  Coaching hub / school proximity
[ 🏥 EMERGENCY ROUTE: OPEN ]   ←  Hospital corridor protection
[ 🚒 FIRE STATION: CLEAR ]     ←  Fire station egress priority
```

Cold data becomes a human-centric dispatch priority.

---

### `MODULE_07` — Debrief 🟡 _(Model Accountability)_

We don't hide the algorithm's mistakes — we **highlight them**.

The Debrief page tracks every instance where the LightGBM model's duration prediction drifted from reality. By plotting spatial errors and generating "Drift Notes," we give ML engineers the exact data needed to retrain and improve the pipeline.

> _Accountability isn't a post-mortem. It's a retraining signal._

---

## 💻 Technical Stack

### Frontend

| Technology         | Role                                |
| ------------------ | ----------------------------------- |
| React.js / Next.js | Fast, component-based rendering     |
| Tailwind CSS       | High-density semantic color grading |
| Recharts / D3.js   | Telemetry visualization             |

### Backend & ML Pipeline

| Technology           | Role                                           |
| -------------------- | ---------------------------------------------- |
| Python / FastAPI     | High-concurrency API routing                   |
| LightGBM / XGBoost   | Incident duration regression                   |
| PostgreSQL + PostGIS | Geospatial radius queries for Vulnerable Zones |

### Architecture at a Glance

```
┌─────────────────────────────────────────────────────────┐
│                     CLEARPATH OS                        │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌───────────────────┐  │
│  │ Sentinel │───▶│ FastAPI  │───▶│  LightGBM Engine  │  │
│  │ (Reports)│    │ Backend  │    │  (Severity Score) │  │
│  └──────────┘    └────┬─────┘    └────────┬──────────┘  │
│                       │                   │             │
│                  ┌────▼─────┐    ┌────────▼──────────┐  │
│                  │ PostGIS  │    │  Geospatial Check  │  │
│                  │ (500m q) │◀───│  Vulnerable Zones  │  │
│                  └────┬─────┘    └───────────────────┘  │
│                       │                                 │
│                  ┌────▼──────────────────────────────┐  │
│                  │     React Dashboard (Intel Page)   │  │
│                  │     God Mode / Debrief / Sentinel  │  │
│                  └───────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Local Installation

### Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL with PostGIS extension

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/clearpath-os.git
cd clearpath-os

# 2. Setup the Python Virtual Environment (Backend)
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# → Set your DATABASE_URL, PostGIS connection, etc.

# 4. Start the FastAPI server
uvicorn main:app --reload
# Server runs at http://localhost:8000

# 5. Setup the Frontend (new terminal)
cd ../frontend
npm install
npm run dev
# App runs at http://localhost:3000
```

### Environment Variables

```env
DATABASE_URL=postgresql://user:password@localhost:5432/clearpath
POSTGIS_ENABLED=true
VULNERABLE_ZONE_RADIUS_METERS=500
MODEL_PATH=./models/lightgbm_incident.pkl
```

---

## 📊 Model Accountability — The Debrief Protocol

ClearPath OS surfaces model failure, not just model success.

| Accountability Feature  | Description                                                |
| ----------------------- | ---------------------------------------------------------- |
| **Drift Notes**         | Auto-generated when prediction error exceeds threshold     |
| **Spatial Error Plots** | Maps where the model consistently under/over-predicts      |
| **Retrain Flags**       | Triggers when drift accumulates above retraining threshold |
| **ROC-AUC Live Feed**   | Real-time precision/recall visible to dispatchers          |

> The Debrief page isn't for optics. It's a retraining signal for engineers — logged, plotted, and acted on.

---

## 👥 Team

| Name | Role                                   |
| ---- | -------------------------------------- |
| —    | ML Engineering — LightGBM Pipeline     |
| —    | Backend — FastAPI + PostGIS            |
| —    | Frontend — React Dashboard             |
| —    | Civic UX — Dispatcher Interface Design |

---

## 📄 License

MIT License — see [`LICENSE`](./LICENSE) for details.

---

<div align="center">

**ClearPath OS** — _Because the road to a hospital should never be blocked by a pothole report._

`v2.4.1` · Built with Geospatial Empathy · MIT License

</div>
