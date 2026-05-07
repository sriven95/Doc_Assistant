# Doc Assistant — Q&A Service

RAG-based conversational Q&A for clinical staff built on top of the Summary Service.
Two FastAPI services in one repo — Embedding and AI Layer.

---

## Architecture

```
doc_assistant_qa/
├── embedding_service/     FastAPI (port 8001) — chunks + embeds clinical notes
├── ai_layer_service/      FastAPI (port 8002) — Q&A orchestration
├── shared/                Used by both services
├── data/input/            input.xlsx  (raw clinical notes)
├── data/output/           output.xlsx (patient summaries from summary service)
└── docker-compose.yml     Qdrant + Redis
```

---

## Prerequisites

- Python 3.11
- Docker (for Qdrant + Redis)
- Service account JSON from Google Cloud
- `input.xlsx` and `output.xlsx` from the summary service

---

## Setup

### 1. Start Qdrant and Redis

```bash
docker-compose up -d
```

Qdrant runs on `localhost:6565`
Redis runs on `localhost:6379`

### 2. Update .env

```bash
cp .env.example .env
# Edit .env — set GOOGLE_APPLICATION_CREDENTIALS to your JSON path
```

### 3. Install dependencies and run Embedding Service

```bash
cd embedding_service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### 4. Install dependencies and run AI Layer Service

```bash
cd ai_layer_service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002
```

---

## Usage — Step by Step

### Step 1 — Bulk embed all patients (one time)

```
POST http://localhost:8001/api/v1/embed/bulk
Body: {}
→ Returns job_id
```

### Step 2 — Poll progress

```
GET http://localhost:8001/api/v1/embed/status/{job_id}
→ Watch processed count
```

### Step 3 — Open a patient conversation

```
POST http://localhost:8002/api/v1/chat/start
Body: { "person_id": "P001" }
→ Returns patient summary + session created (15 min TTL)
```

### Step 4 — Ask a question

```
POST http://localhost:8002/api/v1/chat/ask
Body: { "person_id": "P001", "question": "What SDOH risks does this patient have?" }
→ Returns grounded answer + source citations
```

### Step 5 — Ask follow-up questions (within 15 min)

```
POST http://localhost:8002/api/v1/chat/ask
Body: { "person_id": "P001", "question": "Tell me more about the housing situation." }
→ Gemini uses prior conversation context
```

### Step 6 — When patient summary is updated

```
POST http://localhost:8001/api/v1/embed/patient
Body: { "person_id": "P001" }
→ Old vectors deleted, patient re-embedded with latest notes
```

---

## API Reference

### Embedding Service (port 8001)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/embed/bulk` | Embed all patients (one time) |
| POST | `/api/v1/embed/patient` | Re-embed one patient |
| GET | `/api/v1/embed/status/{job_id}` | Poll bulk job |
| GET | `/health` | Health check |

### AI Layer Service (port 8002)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/chat/start` | Open conversation, get summary |
| POST | `/api/v1/chat/ask` | Ask question, get answer |
| GET | `/api/v1/chat/history/{person_id}` | View conversation history |
| DELETE | `/api/v1/chat/session/{person_id}` | Clear session manually |
| GET | `/health` | Health check |

---

## Session Behaviour

- Session TTL = **15 minutes fixed** from creation time
- TTL does **NOT reset** on each message
- After 15 min session expires — next `/chat/start` creates a fresh session
- Max **20 conversation turns** kept in history

---

## Swagger Docs

- Embedding Service: http://localhost:8001/docs
- AI Layer Service:  http://localhost:8002/docs
