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
    """Webhook for Vapi voice agent callbacks - saves patient data from call"""
    try:
        logger.info(f"Vapi Webhook received")

        # Extract call data from Vapi webhook
        messages = request_body.get("messages", [])
        call_summary = request_body.get("summary", {})
        structured_data = request_body.get("structuredData", {})

        # If structured data is provided, use it directly
        if structured_data and isinstance(structured_data, dict):
            data = structured_data
            logger.info(f"Using structured data from Vapi: {data}")
        else:
            # Parse from call summary if available
            data = call_summary if isinstance(call_summary, dict) else {}
            logger.info(f"Using call summary: {data}")

        # If we have minimal data, extract from message transcript
        if not data or len(data) < 3:
            # Parse from messages transcript
            transcript = "\n".join([f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in messages]) if messages else ""
            logger.info(f"Transcript: {transcript}")

            # Try to extract key fields from transcript
            data = {
                "first_name": call_summary.get("first_name") or data.get("first_name", ""),
                "last_name": call_summary.get("last_name") or data.get("last_name", ""),
                "date_of_birth": call_summary.get("date_of_birth") or data.get("date_of_birth", ""),
                "sex": call_summary.get("sex") or data.get("sex", ""),
                "phone_number": call_summary.get("phone_number") or data.get("phone_number", ""),
                "address_line_1": call_summary.get("address_line_1") or data.get("address_line_1", ""),
                "city": call_summary.get("city") or data.get("city", ""),
                "state": call_summary.get("state") or data.get("state", ""),
                "zip_code": call_summary.get("zip_code") or data.get("zip_code", ""),
            }

        # Validate we have required fields
        required_fields = ["first_name", "last_name", "date_of_birth", "sex", "phone_number", "address_line_1", "city", "state", "zip_code"]
        missing_fields = [f for f in required_fields if not data.get(f)]

        if missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}. Data: {data}")
            return {"success": False, "message": f"Missing required fields: {missing_fields}"}

        # Convert date format MM/DD/YYYY to YYYY-MM-DD
        dob = data.get("date_of_birth", "")
        if dob and "/" in dob:
            try:
                parts = dob.split("/")
                if len(parts) == 3:
                    # Convert MM/DD/YYYY to YYYY-MM-DD
                    data["date_of_birth"] = f"{parts[2]}-{parts[0]}-{parts[1]}"
            except:
                pass

        # Try to create patient
        try:
            patient_data = schemas.PatientCreate(**data)
            new_patient = crud.create_patient(db, patient_data)
            logger.info(f"✅ Patient saved successfully: {new_patient.patient_id} - {new_patient.first_name} {new_patient.last_name}")

            return {
                "success": True,
                "patient_id": new_patient.patient_id,
                "message": f"Patient {new_patient.first_name} {new_patient.last_name} registered successfully"
            }
        except Exception as patient_error:
            logger.error(f"Error creating patient: {str(patient_error)}")
            return {"success": False, "error": f"Patient creation failed: {str(patient_error)}"}

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return {"success": False, "error": str(e)}

@app.post("/vapi/save-patient")
async def vapi_save_patient(request_body: dict, db: Session = Depends(get_db)):
    """
    Dedicated Vapi webhook endpoint for save_patient tool calls.
    Accepts Vapi custom-tool payload and saves patient to database.

    Supports multiple Vapi payload formats:
    1. Direct arguments: {first_name, last_name, ...}
    2. Webhook wrapper: {message: {toolCallList: [...]}}
    """
    try:
        logger.info("🔔 Vapi save-patient webhook received")
        logger.info(f"Request body keys: {list(request_body.keys())}")

        # Check if this is a direct custom-tool request (no wrapper)
        # Vapi custom tools send arguments directly
        if "message" not in request_body and ("first_name" in request_body or "arguments" in request_body):
            logger.info("📍 Detected direct Vapi custom-tool request format")

            # Extract arguments - could be direct or nested
            arguments = request_body if "first_name" in request_body else request_body.get("arguments", {})

            if not arguments:
                logger.error("No patient arguments found")
                return {"error": "Missing patient data"}

            logger.info(f"Processing direct tool call with fields: {list(arguments.keys())}")

            try:
                # Make a mutable copy of arguments for normalization
                normalized_args = dict(arguments)

                # Convert date_of_birth to YYYY-MM-DD format (handle multiple input formats)
                dob = normalized_args.get("date_of_birth", "")
                if dob:
                    try:
                        parts = str(dob).replace("-", "/").split("/")
                        if len(parts) == 3:
                            # Detect format: if first part > 12, it's DD-MM-YYYY, else assume MM-DD-YYYY
                            m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
                            if m > 12:  # First part is day (DD-MM-YYYY format)
                                normalized_args["date_of_birth"] = f"{y}-{d:02d}-{m:02d}"
                            else:  # MM-DD-YYYY format
                                normalized_args["date_of_birth"] = f"{y}-{m:02d}-{d:02d}"
                            logger.info(f"Converted date_of_birth from {dob} to {normalized_args['date_of_birth']}")
                    except Exception as date_error:
                        logger.warning(f"Failed to convert date {dob}: {str(date_error)}")

                # Normalize sex field (capitalize first letter)
                if "sex" in normalized_args:
                    sex_value = normalized_args["sex"]
                    if isinstance(sex_value, str):
                        # Capitalize: Male, Female, Other, Decline to Answer
                        sex_lower = sex_value.lower().strip()
                        if sex_lower == "decline to answer":
                            normalized_args["sex"] = "Decline to Answer"
                        elif sex_lower in ["male", "female", "other"]:
                            normalized_args["sex"] = sex_lower.capitalize()
                        logger.info(f"Normalized sex from {sex_value} to {normalized_args['sex']}")

                # Clean phone number (remove spaces, dashes, take last 10 digits)
                if "phone_number" in normalized_args:
                    phone = str(normalized_args["phone_number"]).replace(" ", "").replace("-", "").replace(".", "")
                    # Take last 10 digits
                    phone = phone[-10:] if len(phone) >= 10 else phone
                    normalized_args["phone_number"] = phone
                    logger.info(f"Normalized phone_number to {phone}")

                # Check for existing patient by phone number
                phone_number = normalized_args.get("phone_number")
                if phone_number:
                    existing = crud.get_patient_by_phone(db, phone_number)
                    if existing:
                        logger.warning(f"Patient already exists with phone {phone_number}")
                        return {"error": f"Patient with phone {phone_number} already exists"}

                # Validate and create patient
                patient_data = schemas.PatientCreate(**normalized_args)
                logger.info(f"✅ Validation passed for patient: {normalized_args.get('first_name')} {normalized_args.get('last_name')}")

                new_patient = crud.create_patient(db, patient_data)
                logger.info(f"✅ Patient saved successfully: {new_patient.patient_id} - {new_patient.first_name} {new_patient.last_name}")

                return {"success": True, "patient_id": new_patient.patient_id, "message": f"Patient {new_patient.first_name} {new_patient.last_name} registered successfully"}

            except ValueError as ve:
                logger.error(f"Validation error: {str(ve)}")
                return {"error": f"Validation failed: {str(ve)}"}
            except Exception as e:
                logger.error(f"Error saving patient: {str(e)}")
                return {"error": f"Patient could not be saved: {str(e)}"}

        # Original webhook format with message wrapper
        message = request_body.get("message", {})
        if not message:
            logger.error("No 'message' in request body")
            return {
                "results": [{
                    "toolCallId": "unknown",
                    "error": "Invalid payload: missing 'message'"
                }]
            }

        # Extract tool call list
        tool_call_list = message.get("toolCallList", [])
        if not tool_call_list:
            logger.error("No tool calls in message")
            return {
                "results": [{
                    "toolCallId": "unknown",
                    "error": "Invalid payload: no toolCallList"
                }]
            }

        results = []

        # Process each tool call
        for tool_call in tool_call_list:
            tool_call_id = tool_call.get("id")
            if not tool_call_id:
                logger.error("Tool call missing 'id'")
                results.append({
                    "toolCallId": "unknown",
                    "error": "Tool call missing id"
                })
                continue

            # Support both Vapi payload formats
            tool_name = None
            arguments = None

            # Format 1: direct name + arguments
            if "name" in tool_call and tool_call.get("name") == "save_patient":
                tool_name = tool_call.get("name")
                arguments = tool_call.get("arguments", {})

            # Format 2: function.name + function.arguments
            elif "function" in tool_call:
                function = tool_call.get("function", {})
                if function.get("name") == "save_patient":
                    tool_name = function.get("name")
                    arguments = function.get("arguments", {})

            # Check if we found save_patient
            if tool_name != "save_patient":
                logger.warning(f"Tool call is not save_patient, skipping: {tool_call.get('name') or tool_call.get('function', {}).get('name')}")
                results.append({
                    "toolCallId": tool_call_id,
                    "error": f"Unknown tool: {tool_name or 'unknown'}"
                })
                continue

            if not arguments:
                logger.error(f"Tool call {tool_call_id} missing arguments")
                results.append({
                    "toolCallId": tool_call_id,
                    "error": "Missing arguments"
                })
                continue

            logger.info(f"Processing save_patient call {tool_call_id} with fields: {list(arguments.keys())}")

            try:
                # Make a mutable copy of arguments for normalization
                normalized_args = dict(arguments)

                # Convert date_of_birth to YYYY-MM-DD format (handle multiple input formats)
                dob = normalized_args.get("date_of_birth", "")
                if dob:
                    try:
                        parts = str(dob).replace("-", "/").split("/")
                        if len(parts) == 3:
                            # Detect format: if first part > 12, it's DD-MM-YYYY, else assume MM-DD-YYYY
                            m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
                            if m > 12:  # First part is day (DD-MM-YYYY format)
                                normalized_args["date_of_birth"] = f"{y}-{d:02d}-{m:02d}"
                            else:  # MM-DD-YYYY format
                                normalized_args["date_of_birth"] = f"{y}-{m:02d}-{d:02d}"
                            logger.info(f"Converted date_of_birth from {dob} to {normalized_args['date_of_birth']}")
                    except Exception as date_error:
                        logger.warning(f"Failed to convert date {dob}: {str(date_error)}")

                # Normalize sex field (capitalize first letter)
                if "sex" in normalized_args:
                    sex_value = normalized_args["sex"]
                    if isinstance(sex_value, str):
                        sex_lower = sex_value.lower().strip()
                        if sex_lower == "decline to answer":
                            normalized_args["sex"] = "Decline to Answer"
                        elif sex_lower in ["male", "female", "other"]:
                            normalized_args["sex"] = sex_lower.capitalize()
                        logger.info(f"Normalized sex from {sex_value} to {normalized_args['sex']}")

                # Clean phone number (remove spaces, dashes, take last 10 digits)
                if "phone_number" in normalized_args:
                    phone = str(normalized_args["phone_number"]).replace(" ", "").replace("-", "").replace(".", "")
                    phone = phone[-10:] if len(phone) >= 10 else phone
                    normalized_args["phone_number"] = phone
                    logger.info(f"Normalized phone_number to {phone}")

                # Check for existing patient by phone number (duplicate detection)
                phone_number = normalized_args.get("phone_number")
                if phone_number:
                    existing = crud.get_patient_by_phone(db, phone_number)
                    if existing:
                        logger.warning(f"Patient already exists with phone {phone_number}")
                        results.append({
                            "toolCallId": tool_call_id,
                            "error": f"Patient with phone {phone_number} already exists"
                        })
                        continue

                # Validate arguments against existing PatientCreate schema
                patient_data = schemas.PatientCreate(**normalized_args)
                logger.info(f"✅ Validation passed for patient: {normalized_args.get('first_name')} {normalized_args.get('last_name')}")

                # Reuse existing CRUD logic
                new_patient = crud.create_patient(db, patient_data)
                logger.info(f"✅ Patient saved successfully: {new_patient.patient_id} - {new_patient.first_name} {new_patient.last_name}")

                results.append({
                    "toolCallId": tool_call_id,
                    "result": "Patient saved successfully"
                })

            except ValueError as ve:
                logger.error(f"Validation error for {tool_call_id}: {str(ve)}")
                results.append({
                    "toolCallId": tool_call_id,
                    "error": f"Patient could not be saved: {str(ve)}"
                })
            except Exception as patient_error:
                logger.error(f"Error for {tool_call_id}: {str(patient_error)}")
                results.append({
                    "toolCallId": tool_call_id,
                    "error": f"Patient could not be saved: {str(patient_error)}"
                })

        # Return Vapi-compliant response (always HTTP 200)
        return {"results": results}

    except Exception as e:
        logger.error(f"Vapi webhook error: {str(e)}")
        return {
            "results": [{
                "toolCallId": "unknown",
                "error": f"Invalid request: {str(e)}"
            }]
        }


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
