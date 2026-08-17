from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
import models
from models import Patient
from schemas import PatientCreate, PatientUpdate
from datetime import date
from typing import Any, List, Optional

def create_patient(db: Session, patient: PatientCreate) -> Patient:
    """Create a new patient record"""
    db_patient = Patient(**patient.model_dump())
    try:
        db.add(db_patient)
        db.commit()
        db.refresh(db_patient)
    except Exception:
        db.rollback()
        raise
    return db_patient

def get_patient(db: Session, patient_id: str) -> Optional[Patient]:
    """Get a patient by ID"""
    return db.query(Patient).filter(
        and_(Patient.patient_id == patient_id, Patient.deleted_at.is_(None))
    ).first()

def get_all_patients(db: Session, skip: int = 0, limit: int = 100) -> List[Patient]:
    """Get all non-deleted patients"""
    return db.query(Patient).filter(
        Patient.deleted_at.is_(None)
    ).offset(skip).limit(limit).all()

def search_patients(
    db: Session,
    last_name: Optional[str] = None,
    date_of_birth: Optional[date] = None,
    phone_number: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Patient]:
    """Search patients by optional filters"""
    query = db.query(Patient).filter(Patient.deleted_at.is_(None))

    if last_name:
        query = query.filter(Patient.last_name.ilike(f"%{last_name}%"))
    if date_of_birth:
        query = query.filter(Patient.date_of_birth == date_of_birth)
    if phone_number:
        query = query.filter(Patient.phone_number == phone_number)

    return query.offset(skip).limit(limit).all()

def update_patient(db: Session, patient_id: str, patient_update: PatientUpdate) -> Optional[Patient]:
    """Update an existing patient"""
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        return None

    update_data = patient_update.model_dump(exclude_unset=True)
    new_phone = update_data.get("phone_number")
    if new_phone:
        existing = get_patient_by_phone(db, new_phone)
        if existing and existing.patient_id != patient_id:
            raise ValueError(f"Patient with phone {new_phone} already exists")

    for key, value in update_data.items():
        setattr(db_patient, key, value)

    try:
        db.add(db_patient)
        db.commit()
        db.refresh(db_patient)
    except Exception:
        db.rollback()
        raise
    return db_patient

def delete_patient(db: Session, patient_id: str) -> bool:
    """Soft delete a patient (set deleted_at timestamp)"""
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        return False

    from datetime import datetime
    db_patient.deleted_at = datetime.utcnow()
    try:
        db.add(db_patient)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True

def get_patient_by_phone(db: Session, phone_number: str) -> Optional[Patient]:
    """Get a patient by phone number (for duplicate detection)"""
    return db.query(Patient).filter(
        and_(Patient.phone_number == phone_number, Patient.deleted_at.is_(None))
    ).first()


def create_call_session(
    db: Session,
    *,
    call_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    livekit_room_name: Optional[str] = None,
    livekit_participant_identity: Optional[str] = None,
    caller_phone: Optional[str] = None,
    status: str = "started",
    language: Optional[str] = "English",
) -> models.CallSession:
    """Create a durable call-history row for dashboard visibility."""
    call = models.CallSession(
        call_id=call_id,
        patient_id=patient_id,
        livekit_room_name=livekit_room_name,
        livekit_participant_identity=livekit_participant_identity,
        caller_phone=caller_phone,
        status=status,
        language=language,
    )
    try:
        db.add(call)
        db.commit()
        db.refresh(call)
    except Exception:
        db.rollback()
        raise
    return call


def create_tool_call_log(
    db: Session,
    *,
    tool_name: str,
    success: bool,
    arguments: Optional[dict[str, Any]] = None,
    result_text: Optional[str] = None,
    latency_ms: Optional[int] = None,
    call_id: Optional[str] = None,
    patient_id: Optional[str] = None,
) -> models.ToolCallLog:
    """Persist a voice-agent function/tool call result."""
    log = models.ToolCallLog(
        call_id=call_id,
        patient_id=patient_id,
        tool_name=tool_name,
        arguments=arguments,
        result_text=result_text,
        success=success,
        latency_ms=latency_ms,
    )
    try:
        db.add(log)
        db.commit()
        db.refresh(log)
    except Exception:
        db.rollback()
        raise
    return log


def create_transcript_message(
    db: Session,
    *,
    speaker: str,
    text: str,
    call_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    is_final: bool = True,
    confidence: Optional[float] = None,
) -> models.TranscriptMessage:
    message = models.TranscriptMessage(
        call_id=call_id,
        patient_id=patient_id,
        speaker=speaker,
        text=text,
        is_final=is_final,
        confidence=confidence,
    )
    try:
        db.add(message)
        db.commit()
        db.refresh(message)
    except Exception:
        db.rollback()
        raise
    return message


def create_agent_event(
    db: Session,
    *,
    event_type: str,
    provider: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    call_id: Optional[str] = None,
    patient_id: Optional[str] = None,
) -> models.AgentEvent:
    event = models.AgentEvent(
        call_id=call_id,
        patient_id=patient_id,
        event_type=event_type,
        provider=provider,
        payload=payload,
    )
    try:
        db.add(event)
        db.commit()
        db.refresh(event)
    except Exception:
        db.rollback()
        raise
    return event


def create_llm_token_usage(
    db: Session,
    *,
    provider: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: Optional[int] = None,
    call_id: Optional[str] = None,
    patient_id: Optional[str] = None,
) -> models.LLMTokenUsage:
    usage = models.LLMTokenUsage(
        call_id=call_id,
        patient_id=patient_id,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens or prompt_tokens + completion_tokens,
        latency_ms=latency_ms,
    )
    try:
        db.add(usage)
        db.commit()
        db.refresh(usage)
    except Exception:
        db.rollback()
        raise
    return usage


def create_pipeline_metric(
    db: Session,
    *,
    stage: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    latency_ms: Optional[int] = None,
    duration_ms: Optional[int] = None,
    status: str = "ok",
    payload: Optional[dict[str, Any]] = None,
    call_id: Optional[str] = None,
    patient_id: Optional[str] = None,
) -> models.PipelineMetric:
    metric = models.PipelineMetric(
        call_id=call_id,
        patient_id=patient_id,
        stage=stage,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        duration_ms=duration_ms,
        status=status,
        payload=payload,
    )
    try:
        db.add(metric)
        db.commit()
        db.refresh(metric)
    except Exception:
        db.rollback()
        raise
    return metric


def get_recent_calls(db: Session, skip: int = 0, limit: int = 50) -> List[models.CallSession]:
    return (
        db.query(models.CallSession)
        .order_by(desc(models.CallSession.started_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_call(db: Session, call_id: str) -> Optional[models.CallSession]:
    return db.query(models.CallSession).filter(models.CallSession.call_id == call_id).first()


def get_call_timeline(db: Session, call_id: str) -> dict[str, list[Any]]:
    return {
        "transcripts": (
            db.query(models.TranscriptMessage)
            .filter(models.TranscriptMessage.call_id == call_id)
            .order_by(models.TranscriptMessage.created_at)
            .all()
        ),
        "events": (
            db.query(models.AgentEvent)
            .filter(models.AgentEvent.call_id == call_id)
            .order_by(models.AgentEvent.created_at)
            .all()
        ),
        "tool_calls": (
            db.query(models.ToolCallLog)
            .filter(models.ToolCallLog.call_id == call_id)
            .order_by(models.ToolCallLog.created_at)
            .all()
        ),
        "token_usage": (
            db.query(models.LLMTokenUsage)
            .filter(models.LLMTokenUsage.call_id == call_id)
            .order_by(models.LLMTokenUsage.created_at)
            .all()
        ),
        "pipeline_metrics": (
            db.query(models.PipelineMetric)
            .filter(models.PipelineMetric.call_id == call_id)
            .order_by(models.PipelineMetric.created_at)
            .all()
        ),
    }


def get_dashboard_overview(db: Session) -> dict[str, Any]:
    total_tokens = db.query(func.coalesce(func.sum(models.LLMTokenUsage.total_tokens), 0)).scalar()
    return {
        "active_patients": db.query(Patient).filter(Patient.deleted_at.is_(None)).count(),
        "deleted_patients": db.query(Patient).filter(Patient.deleted_at.is_not(None)).count(),
        "total_calls": db.query(models.CallSession).count(),
        "completed_calls": db.query(models.CallSession).filter(models.CallSession.status == "completed").count(),
        "failed_calls": db.query(models.CallSession).filter(models.CallSession.status.in_(["failed", "dropped"])).count(),
        "tool_calls": db.query(models.ToolCallLog).count(),
        "successful_tool_calls": db.query(models.ToolCallLog).filter(models.ToolCallLog.success.is_(True)).count(),
        "llm_total_tokens": int(total_tokens or 0),
    }
