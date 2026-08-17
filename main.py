from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date, datetime
from pathlib import Path
from typing import Any, List, Optional
import logging
import os
from dotenv import load_dotenv

import models
import schemas
import crud
from database import get_db, init_database, safe_database_url

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_PATH = BASE_DIR / "static" / "dashboard.html"


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def serialize_record(record: Any) -> dict[str, Any]:
    return {
        column.name: _json_value(getattr(record, column.name))
        for column in record.__table__.columns
    }

app = FastAPI(
    title="Patient Registration API",
    description="Voice AI Agent - Patient Registration System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    init_database()
    logger.info("Database initialized: %s", safe_database_url())

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "patient-registration-api"}


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(DASHBOARD_PATH)

@app.get("/patients")
async def list_patients(
    last_name: Optional[str] = Query(None),
    date_of_birth: Optional[date] = Query(None),
    phone_number: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """List patients, optionally filtered by last_name, date_of_birth, or phone_number."""
    try:
        if last_name or date_of_birth or phone_number:
            patients = crud.search_patients(
                db,
                last_name=last_name,
                date_of_birth=date_of_birth,
                phone_number=phone_number,
                skip=skip,
                limit=limit,
            )
        else:
            patients = crud.get_all_patients(db, skip=skip, limit=limit)
        logger.info(f"Retrieved {len(patients)} patients")
        return {
            "data": {"patients": [schemas.PatientResponse.model_validate(p).model_dump() for p in patients]},
            "error": None,
            "status": 200
        }
    except Exception as e:
        logger.error(f"Error listing patients: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/patients/search")
async def search_patients(
    last_name: Optional[str] = Query(None),
    date_of_birth: Optional[date] = Query(None),
    phone_number: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Search patients by optional filters"""
    try:
        patients = crud.search_patients(
            db,
            last_name=last_name,
            date_of_birth=date_of_birth,
            phone_number=phone_number,
            skip=skip,
            limit=limit
        )
        logger.info(f"Search returned {len(patients)} patients")
        return {
            "data": {"patients": [schemas.PatientResponse.model_validate(p).model_dump() for p in patients]},
            "error": None,
            "status": 200
        }
    except Exception as e:
        logger.error(f"Error searching patients: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/patients/{patient_id}")
async def get_patient(patient_id: str, db: Session = Depends(get_db)):
    """Get a specific patient by ID"""
    try:
        patient = crud.get_patient(db, patient_id)
        if not patient:
            logger.warning(f"Patient not found: {patient_id}")
            raise HTTPException(status_code=404, detail="Patient not found")
        patient_data = schemas.PatientResponse.model_validate(patient)
        return {
            "data": patient_data.model_dump(),
            "error": None,
            "status": 200
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving patient {patient_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/patients", status_code=201)
async def create_patient(patient: schemas.PatientCreate, db: Session = Depends(get_db)):
    """Create a new patient record"""
    try:
        existing = crud.get_patient_by_phone(db, patient.phone_number)
        if existing:
            logger.warning(f"Duplicate patient phone: {patient.phone_number}")
            raise HTTPException(
                status_code=422,
                detail=f"Patient with phone {patient.phone_number} already exists"
            )

        new_patient = crud.create_patient(db, patient)
        logger.info(f"Created patient: {new_patient.patient_id}")
        patient_data = schemas.PatientResponse.model_validate(new_patient)
        return {
            "data": patient_data.model_dump(),
            "error": None,
            "status": 201
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating patient: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/patients/{patient_id}")
async def update_patient(
    patient_id: str,
    patient_update: schemas.PatientUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing patient record"""
    try:
        updated_patient = crud.update_patient(db, patient_id, patient_update)
        if not updated_patient:
            logger.warning(f"Patient not found for update: {patient_id}")
            raise HTTPException(status_code=404, detail="Patient not found")

        logger.info(f"Updated patient: {patient_id}")
        patient_data = schemas.PatientResponse.model_validate(updated_patient)
        return {
            "data": patient_data.model_dump(),
            "error": None,
            "status": 200
        }
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error updating patient {patient_id}: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating patient {patient_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/patients/{patient_id}")
async def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    """Soft delete a patient record"""
    try:
        success = crud.delete_patient(db, patient_id)
        if not success:
            logger.warning(f"Patient not found for deletion: {patient_id}")
            raise HTTPException(status_code=404, detail="Patient not found")

        logger.info(f"Deleted patient: {patient_id}")
        return {
            "data": {"patient_id": patient_id, "deleted": True},
            "error": None,
            "status": 200
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting patient {patient_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/patients/{patient_id}/check-duplicate")
async def check_duplicate(patient_id: str, db: Session = Depends(get_db)):
    """Check if a patient already exists by phone number"""
    try:
        patient = crud.get_patient(db, patient_id)
        if patient:
            return {
                "exists": True,
                "patient": schemas.PatientResponse.model_validate(patient)
            }
        return {"exists": False}
    except Exception as e:
        logger.error(f"Error checking duplicate: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/dashboard/overview")
async def dashboard_overview(db: Session = Depends(get_db)):
    """High-level dashboard counters for patient intake and voice-agent activity."""
    try:
        return {
            "data": crud.get_dashboard_overview(db),
            "error": None,
            "status": 200,
        }
    except Exception as e:
        logger.error(f"Error loading dashboard overview: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/calls")
async def list_calls(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List recent voice-agent calls for the dashboard."""
    try:
        calls = crud.get_recent_calls(db, skip=skip, limit=limit)
        return {
            "data": {"calls": [serialize_record(call) for call in calls]},
            "error": None,
            "status": 200,
        }
    except Exception as e:
        logger.error(f"Error listing calls: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/calls/{call_id}")
async def get_call(call_id: str, db: Session = Depends(get_db)):
    """Retrieve one voice-agent call summary."""
    try:
        call = crud.get_call(db, call_id)
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        return {
            "data": serialize_record(call),
            "error": None,
            "status": 200,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving call {call_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/calls/{call_id}/timeline")
async def get_call_timeline(call_id: str, db: Session = Depends(get_db)):
    """Retrieve transcripts, events, tools, tokens, and pipeline metrics for a call."""
    try:
        call = crud.get_call(db, call_id)
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        timeline = crud.get_call_timeline(db, call_id)
        return {
            "data": {
                "call": serialize_record(call),
                **{
                    key: [serialize_record(item) for item in values]
                    for key, values in timeline.items()
                },
            },
            "error": None,
            "status": 200,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving call timeline {call_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/metrics/tokens")
async def list_token_usage(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List recent LLM token-usage rows for cost/latency dashboarding."""
    try:
        rows = (
            db.query(models.LLMTokenUsage)
            .order_by(desc(models.LLMTokenUsage.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {
            "data": {"token_usage": [serialize_record(row) for row in rows]},
            "error": None,
            "status": 200,
        }
    except Exception as e:
        logger.error(f"Error listing token usage: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/metrics/pipeline")
async def list_pipeline_metrics(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List recent VAD/STT/LLM/TTS pipeline latency metrics."""
    try:
        rows = (
            db.query(models.PipelineMetric)
            .order_by(desc(models.PipelineMetric.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {
            "data": {"pipeline_metrics": [serialize_record(row) for row in rows]},
            "error": None,
            "status": 200,
        }
    except Exception as e:
        logger.error(f"Error listing pipeline metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/tool-calls")
async def list_tool_calls(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List recent tool/function calls made by the voice agent."""
    try:
        rows = (
            db.query(models.ToolCallLog)
            .order_by(desc(models.ToolCallLog.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {
            "data": {"tool_calls": [serialize_record(row) for row in rows]},
            "error": None,
            "status": 200,
        }
    except Exception as e:
        logger.error(f"Error listing tool calls: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    print(f"🚀 Starting Patient Registration API on port {port}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
