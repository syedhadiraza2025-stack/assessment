from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
import uuid
from database import Base
from datetime import datetime


def uuid_str() -> str:
    return str(uuid.uuid4())


class Patient(Base):
    __tablename__ = "patients"

    patient_id = Column(String(36), primary_key=True, default=uuid_str)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    sex = Column(String(20), nullable=False)  # Male, Female, Other, Decline to Answer
    phone_number = Column(String(10), nullable=False)
    email = Column(String(254), nullable=True)
    address_line_1 = Column(String(255), nullable=False)
    address_line_2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(2), nullable=False)
    zip_code = Column(String(10), nullable=False)
    insurance_provider = Column(String(255), nullable=True)
    insurance_member_id = Column(String(255), nullable=True)
    preferred_language = Column(String(50), default="English", nullable=True)
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(10), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("char_length(first_name) BETWEEN 1 AND 50", name="ck_patients_first_name_len"),
        CheckConstraint("char_length(last_name) BETWEEN 1 AND 50", name="ck_patients_last_name_len"),
        CheckConstraint("date_of_birth < CURRENT_DATE", name="ck_patients_dob_not_future"),
        CheckConstraint("sex IN ('Male', 'Female', 'Other', 'Decline to Answer')", name="ck_patients_sex"),
        CheckConstraint("char_length(phone_number) = 10", name="ck_patients_phone_len"),
        CheckConstraint("char_length(state) = 2", name="ck_patients_state_len"),
        CheckConstraint("char_length(zip_code) IN (5, 9)", name="ck_patients_zip_len"),
        Index(
            "uq_patients_active_phone",
            "phone_number",
            unique=True,
            postgresql_where=deleted_at.is_(None),
        ),
        Index("ix_patients_last_name", "last_name"),
        Index("ix_patients_dob", "date_of_birth"),
    )

    def __repr__(self):
        return f"<Patient {self.first_name} {self.last_name}>"


class CallSession(Base):
    __tablename__ = "calls"

    call_id = Column(String(36), primary_key=True, default=uuid_str)
    patient_id = Column(String(36), ForeignKey("patients.patient_id", ondelete="SET NULL"), nullable=True)
    livekit_room_name = Column(String(255), nullable=True)
    livekit_participant_identity = Column(String(255), nullable=True)
    caller_phone = Column(String(20), nullable=True)
    status = Column(String(30), default="started", nullable=False)
    language = Column(String(50), default="English", nullable=True)
    summary = Column(Text, nullable=True)
    final_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_calls_started_at", "started_at"),
        Index("ix_calls_status", "status"),
        Index("ix_calls_patient_id", "patient_id"),
        Index("ix_calls_livekit_room", "livekit_room_name"),
    )


class TranscriptMessage(Base):
    __tablename__ = "transcripts"

    transcript_id = Column(String(36), primary_key=True, default=uuid_str)
    call_id = Column(String(36), ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=True)
    patient_id = Column(String(36), ForeignKey("patients.patient_id", ondelete="SET NULL"), nullable=True)
    speaker = Column(String(30), nullable=False)
    text = Column(Text, nullable=False)
    is_final = Column(Boolean, default=True, nullable=False)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_transcripts_call_created_at", "call_id", "created_at"),
        Index("ix_transcripts_patient_id", "patient_id"),
    )


class AgentEvent(Base):
    __tablename__ = "agent_events"

    event_id = Column(String(36), primary_key=True, default=uuid_str)
    call_id = Column(String(36), ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=True)
    patient_id = Column(String(36), ForeignKey("patients.patient_id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(80), nullable=False)
    provider = Column(String(80), nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_agent_events_call_created_at", "call_id", "created_at"),
        Index("ix_agent_events_type", "event_type"),
    )


class ToolCallLog(Base):
    __tablename__ = "tool_calls"

    id = Column(String(36), primary_key=True, default=uuid_str)
    call_id = Column(String(36), ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=True)
    patient_id = Column(String(36), ForeignKey("patients.patient_id", ondelete="SET NULL"), nullable=True)
    tool_name = Column(String(100), nullable=False)
    arguments = Column(JSON, nullable=True)
    result_text = Column(Text, nullable=True)
    success = Column(Boolean, default=False, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_tool_calls_call_created_at", "call_id", "created_at"),
        Index("ix_tool_calls_patient_id", "patient_id"),
        Index("ix_tool_calls_tool_name", "tool_name"),
    )


class LLMTokenUsage(Base):
    __tablename__ = "llm_token_usage"

    usage_id = Column(String(36), primary_key=True, default=uuid_str)
    call_id = Column(String(36), ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=True)
    patient_id = Column(String(36), ForeignKey("patients.patient_id", ondelete="SET NULL"), nullable=True)
    provider = Column(String(80), nullable=False)
    model = Column(String(120), nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_llm_usage_call_created_at", "call_id", "created_at"),
        Index("ix_llm_usage_patient_id", "patient_id"),
        Index("ix_llm_usage_provider_model", "provider", "model"),
    )


class PipelineMetric(Base):
    __tablename__ = "pipeline_metrics"

    metric_id = Column(String(36), primary_key=True, default=uuid_str)
    call_id = Column(String(36), ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=True)
    patient_id = Column(String(36), ForeignKey("patients.patient_id", ondelete="SET NULL"), nullable=True)
    stage = Column(String(40), nullable=False)  # vad, stt, llm, tts, telephony
    provider = Column(String(80), nullable=True)
    model = Column(String(120), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    status = Column(String(30), default="ok", nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_pipeline_metrics_call_created_at", "call_id", "created_at"),
        Index("ix_pipeline_metrics_stage", "stage"),
        Index("ix_pipeline_metrics_patient_id", "patient_id"),
    )
