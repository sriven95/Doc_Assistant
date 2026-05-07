# Doc Assistant — Summary Generation Service

A production-ready **FastAPI async service** that reads patient clinical notes
from an Excel file, generates AI-powered summaries using **Gemini Flash 2.5**,
and supports incremental updates when patients return with new events.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Folder Structure](#folder-structure)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Service](#running-the-service)
- [API Reference](#api-reference)
- [Docker](#docker)
- [Testing](#testing)
- [Excel Format](#excel-format)
- [How It Works](#how-it-works)

---

## Overview

| Property | Value |
|---|---|
| Framework | FastAPI (async) |
| AI Model | Gemini Flash 2.5 |
| Storage | Excel (POC) |
| Python | 3.10+ |

### Two Modes

| Mode | Trigger | Description |
|---|---|---|
| **Bulk (one-time)** | `POST /api/v1/generate-summaries` | Processes entire input Excel, generates summary for every patient |
| **Update (incremental)** | `POST /api/v1/update-summary` | When a patient returns with a new event, updates their existing summary |

---

## Architecture

```
doc_assistant_summary/
│
├── app/                        # All application code
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Settings (env vars, column names)
│   │
│   ├── api/v1/routes/          # API layer
│   │   └── summary.py          # All 4 endpoints
│   │
│   ├── core/                   # Cross-cutting concerns
│   │   └── logging.py          # Structured logging setup
│   │
│   ├── models/                 # Data models
│   │   └── schemas.py          # Pydantic request/response schemas
│   │
│   ├── services/               # Business logic
│   │   ├── excel_service.py    # Excel read/write operations
│   │   ├── gemini_service.py   # Gemini API calls
│   │   └── summary_service.py  # Bulk + update orchestration
│   │
│   └── utils/                  # Shared utilities
│       └── prompt_builder.py   # Gemini prompt construction
│
├── data/
│   ├── input/                  # Drop input.xlsx here
│   └── output/                 # output.xlsx written here
│
├── tests/                      # Unit tests
├── logs/                       # Application logs
│
├── .env.example                # Environment variable template
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Local container orchestration
└── requirements.txt            # Python dependencies
```

---

## Prerequisites

- Python **3.10+**
- A **Gemini API key** → https://aistudio.google.com/app/apikey
- Your input Excel file with the correct columns (see [Excel Format](#excel-format))

---

## Setup & Installation

### 1. Clone / download the project

```bash
cd doc_assistant_summary
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 5. Add your input Excel

```bash
# Place your file here:
data/input/input.xlsx
```

---

## Configuration

All configuration lives in `.env`:

| Variable | Description | Default |
|---|---|---|
| `GEMINI_API_KEY` | Your Gemini API key | *required* |
| `GEMINI_MODEL` | Model name | `gemini-2.5-flash` |
| `INPUT_FILE` | Path to input Excel | `data/input/input.xlsx` |
| `OUTPUT_FILE` | Path to output Excel | `data/output/output.xlsx` |
| `MAX_CONCURRENT_CALLS` | Parallel Gemini calls | `5` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `APP_ENV` | Environment tag | `development` |

---

## Running the Service

### Development

```bash
uvicorn app.main:app --reload --port 8000
```

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Swagger UI

```
http://localhost:8000/docs
```

### ReDoc

```
http://localhost:8000/redoc
```

---

## API Reference

### `POST /api/v1/generate-summaries`
Trigger one-time bulk summary generation for all patients.

```json
Request:  { "file_path": "data/input/input.xlsx" }
Response: { "job_id": "uuid", "status": "queued", "total_patients": 0 }
```

### `POST /api/v1/update-summary`
Update a single patient's summary when they return with a new event.

```json
Request:  { "person_id": "P123", "event_id": "E999" }
Response: { "person_id": "P123", "status": "updated", "summary_chain": "..." }
```

### `GET /api/v1/summary/{person_id}`
Fetch the current stored summary for a patient.

```json
Response: { "person_id": "P123", "status": "found", "main_subject": "...", "summary_chain": "..." }
```

### `GET /api/v1/status/{job_id}`
Poll bulk job progress.

```json
Response: { "job_id": "uuid", "status": "completed", "processed": 142, "failed": 0 }
```

### `GET /health`
Health check.

```json
Response: { "status": "ok" }
```

---

## Docker

### Build and run

```bash
docker-compose up --build
```

### Run in background

```bash
docker-compose up -d
```

### Stop

```bash
docker-compose down
```

---

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

---

## Excel Format

### Input Excel (`data/input/input.xlsx`)

| Column | Required | Description |
|---|---|---|
| `event_id` | ✅ | Unique ID for each clinical event |
| `person_id` | ✅ | Patient identifier — groups multiple events |
| `doc_type` | ✅ | Type of clinical note |
| `plain_scrubbed_text` | ✅ | PHI-free clinical note text sent to Gemini |
| `run_id` | optional | Processing run reference |
| `model_id` | optional | Previous model used |
| `model_processed_at` | optional | Previous processing timestamp |
| `firstname` | ❌ ignored | Never sent to Gemini |
| `lastname` | ❌ ignored | Never sent to Gemini |
| `scrubbed_embedding` | ❌ ignored | Not used in this service |
| `event_end_dt_tm` | ❌ ignored | Row order used instead |

### Output Excel (`data/output/output.xlsx`)

| Column | Description |
|---|---|
| `person_id` | Patient identifier |
| `main_subject` | Overall patient clinical picture |
| `summary_chain` | Chained summaries newest → oldest |
| `processed_event_ids` | All event_ids included |
| `event_count` | Number of events processed |
| `model_id` | Gemini model used |
| `generated_at` | First creation timestamp |
| `last_updated_at` | Last update timestamp |

---

## How It Works

### Bulk Flow
```
Input Excel → Group by person_id → Keep natural row order (newest first)
→ Build Gemini prompt (main subject + event chain) → Async Gemini calls
→ Write one row per patient to Output Excel
```

### Update Flow
```
API: person_id + new event_id
→ Check Output Excel: summary exists?
  NO  → Generate fresh (same as bulk for one patient)
  YES → Is event_id already processed?
    YES → Return "already_processed"
    NO  → Place new event at TOP + full regeneration → Overwrite Output Excel
```

### Summary Chain Structure
```
[Main Subject]
Overall patient clinical picture across all events.

[Event: E003 | Most Recent]
Summary of most recent clinical note...

[Event: E002]
Summary of second event...

[Event: E001 | Oldest]
Summary of oldest clinical note...
```

---

## Notes

- `plain_scrubbed_text` is the **only** column sent to Gemini — PHI is never exposed to the AI model
- Row order in the input Excel determines event sequence — **no date column is used**
- The bulk job runs asynchronously — poll `/api/v1/status/{job_id}` for progress
- For production, replace Excel storage with PostgreSQL or MongoDB

---

*Doc Assistant Summary Service · v1.0.0 · Ascension Health · Internal Use Only*
