from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional
import logging
import os
from dotenv import load_dotenv

import models
import schemas
import crud
from database import engine, get_db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

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

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "patient-registration-api"}

@app.get("/patients")
async def list_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """List all patients with optional pagination"""
    try:
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

@app.post("/webhook/vapi")
async def vapi_webhook(request_body: dict, db: Session = Depends(get_db)):
    """Webhook for Vapi voice agent callbacks"""
    try:
        event = request_body.get("event")

        if event == "end-of-call":
            # Handle end of call
            summary = request_body.get("summary", {})
            logger.info(f"Call ended. Summary: {summary}")
            return {"success": True}

        elif event == "save-patient":
            # Handle patient data from voice agent
            data = request_body.get("data", {})

            # Convert date format if needed (MM/DD/YYYY -> YYYY-MM-DD)
            if "date_of_birth" in data:
                dob = data["date_of_birth"]
                if "/" in dob:
                    parts = dob.split("/")
                    if len(parts) == 3:
                        data["date_of_birth"] = f"{parts[2]}-{parts[0]}-{parts[1]}"

            patient_data = schemas.PatientCreate(**data)
            new_patient = crud.create_patient(db, patient_data)
            logger.info(f"Patient saved via webhook: {new_patient.patient_id}")

            return {
                "success": True,
                "patient_id": new_patient.patient_id,
                "message": f"Patient {new_patient.first_name} registered successfully"
            }

        return {"success": True}
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return {"success": False, "error": str(e)}

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
