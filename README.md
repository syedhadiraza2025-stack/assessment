# Voice AI Patient Registration System

## Live Demo

Call the LiveKit-provisioned U.S. phone number to register a patient:

```text
+1 (415) 417-6005
```

REST API:

```text
https://assessment-usm9.onrender.com
```

Operations dashboard:

```text
https://assessment-usm9.onrender.com/dashboard
```

## Overview

This project implements the Voice AI Agent coding challenge: a phone-accessible
medical receptionist that collects U.S. patient demographic information through
natural conversation, confirms it with the caller, stores it durably, and exposes
the records through a REST API.

Core assessment flow:

```text
Caller phone call -> LiveKit voice agent -> Postgres -> FastAPI REST API
```

The dashboard/history tables are bonus infrastructure. They do not replace or
change the required patient-registration behavior.

## Architecture

| Layer | Technology |
| --- | --- |
| Telephony | LiveKit Cloud SIP / trial phone number |
| VAD / endpointing | Deepgram VAD events + STT endpointing; optional Silero when memory allows |
| Noise suppression | Disabled in low-memory Render mode; optional LiveKit Cloud BVC |
| STT | Deepgram nova-2 |
| LLM | Groq, default `openai/gpt-oss-120b` |
| TTS | ElevenLabs |
| Backend | FastAPI |
| Database | PostgreSQL |
| Hosting | Render web service + Render background worker |

The LiveKit worker in `livekit_agent.py` and the FastAPI app in `main.py` share
the same SQLAlchemy service layer and the same Postgres database.

## Assessment Requirements Covered

- Real voice agent pipeline: VAD -> STT -> LLM -> TTS.
- Natural intake conversation, not IVR.
- Required demographics collected before save.
- Optional demographics offered after required fields.
- Full read-back confirmation before saving.
- Server-side validation in Pydantic and database constraints in Postgres.
- Durable persistence across deploys/restarts through Postgres.
- REST API with consistent JSON envelope.
- Soft delete through `deleted_at`.
- Duplicate detection by active phone number.
- Final collected payload logged to stdout.

## Patient Data Model

Required:

- `first_name`
- `last_name`
- `date_of_birth`
- `sex`
- `phone_number`
- `address_line_1`
- `city`
- `state`
- `zip_code`

Optional:

- `email`
- `address_line_2`
- `insurance_provider`
- `insurance_member_id`
- `preferred_language`
- `emergency_contact_name`
- `emergency_contact_phone`

Automatic:

- `patient_id`
- `created_at`
- `updated_at`
- `deleted_at`

## Dashboard / History Tables

Postgres also includes bonus observability tables:

- `calls`
- `transcripts`
- `agent_events`
- `tool_calls`
- `llm_token_usage`
- `pipeline_metrics`

These support a richer dashboard with call history, final payloads, tool results,
transcripts, token usage, latency, and provider-stage metrics.

Dashboard UI:

```text
https://assessment-usm9.onrender.com/dashboard
```

## API

### Health

```bash
curl https://assessment-usm9.onrender.com/health
```

### List / Search Patients

```bash
curl https://assessment-usm9.onrender.com/patients
curl "https://assessment-usm9.onrender.com/patients?last_name=Doe"
curl "https://assessment-usm9.onrender.com/patients?date_of_birth=1990-01-15"
curl "https://assessment-usm9.onrender.com/patients?phone_number=5551234567"
```

### Create Patient

```bash
curl -X POST https://assessment-usm9.onrender.com/patients \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane",
    "last_name": "Smith",
    "date_of_birth": "1985-03-22",
    "sex": "Female",
    "phone_number": "5559876543",
    "address_line_1": "456 Oak Ave",
    "city": "Los Angeles",
    "state": "CA",
    "zip_code": "90001"
  }'
```

### Update / Delete

```bash
curl -X PUT https://assessment-usm9.onrender.com/patients/{patient_id} \
  -H "Content-Type: application/json" \
  -d '{"email": "jane@example.com"}'

curl -X DELETE https://assessment-usm9.onrender.com/patients/{patient_id}
```

### Dashboard Endpoints

```bash
curl https://assessment-usm9.onrender.com/dashboard/overview
curl https://assessment-usm9.onrender.com/calls
curl https://assessment-usm9.onrender.com/calls/{call_id}
curl https://assessment-usm9.onrender.com/calls/{call_id}/timeline
curl https://assessment-usm9.onrender.com/metrics/tokens
curl https://assessment-usm9.onrender.com/metrics/pipeline
curl https://assessment-usm9.onrender.com/tool-calls
```

## Environment Variables

Copy `.env.example` to `.env` locally. On Render, configure these in the web
service and worker service.

```text
PORT=8002
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/voice_agent
LOG_LEVEL=INFO

LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=

GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
DEEPGRAM_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
```

## Local Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local Postgres database named `voice_agent`, set `DATABASE_URL`, then
initialize tables:

```bash
python manage_db.py check
python manage_db.py init
```

Optional local Postgres with Docker:

```bash
docker compose up -d postgres
python manage_db.py check
python manage_db.py init
```

If this is a fresh project and you want to remove all managed tables:

```bash
python manage_db.py reset --confirm DROP_POSTGRES_TABLES
```

Run the API:

```bash
uvicorn main:app --host 0.0.0.0 --port 8002
```

Run the voice agent locally:

```bash
python livekit_agent.py console
```

Run the LiveKit worker:

```bash
python livekit_agent.py dev
```

Production worker command:

```bash
python livekit_agent.py start
```

## Render Deployment

`render.yaml` defines:

- a managed Postgres database,
- a FastAPI web service,
- a LiveKit background worker.

Render should inject the same `DATABASE_URL` into both services. Add the LiveKit,
Groq, Deepgram, and ElevenLabs secrets manually in the Render dashboard.

Render background workers require a paid instance type, so the worker is set to
`starter` in `render.yaml`. The API and Postgres database can remain free while
you are testing.

API start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Worker start command:

```bash
python livekit_agent.py start
```

## Known Limitations

- Not HIPAA compliant; do not store real patient data.
- Dashboard is intentionally unauthenticated for assessment review convenience.
- Seeded demo dashboard data is included so reviewers can inspect the UI before placing a call.
- No staff authentication yet.

## Submission Checklist

- Repository URL.
- Live phone number.
- API base URL.
- Any reviewer notes needed for calling/testing.
