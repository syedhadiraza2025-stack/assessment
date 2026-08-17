#!/usr/bin/env python3
"""LiveKit Agents worker for the patient intake voice pipeline.

Pipeline: caller audio -> Silero VAD -> Deepgram STT -> Groq LLM -> ElevenLabs TTS,
with LiveKit Cloud noise cancellation on the input track. Tool calls write straight
to the same PostgreSQL database the FastAPI backend (main.py) serves over REST.

Run modes:
  python livekit_agent.py console   # talk to it locally via your mic, no telephony
  python livekit_agent.py dev       # connect to LiveKit Cloud and wait for dispatch
  python livekit_agent.py start     # production worker mode for deployment
"""

import os
import asyncio
import logging
import math
import time
import uuid
from typing import Any, Optional

from dotenv import load_dotenv
from pydantic import ValidationError

from livekit import agents
from livekit.agents import Agent, AgentSession, RoomInputOptions, function_tool
from livekit.plugins import deepgram, elevenlabs, groq, silero, noise_cancellation

from database import SessionLocal, init_database, safe_database_url
import crud
import schemas

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("patient-intake-agent")

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # "Sarah" - Mature, Reassuring, Confident

INSTRUCTIONS = """You are a professional patient intake assistant for a healthcare clinic. Your goal is to collect patient registration information through natural, friendly conversation.

REQUIRED FIELDS TO COLLECT (in this order):
1. First Name
2. Last Name
3. Date of Birth (MM/DD/YYYY)
4. Sex (Male, Female, Other, Decline to Answer)
5. Phone Number (10-digit format)
6. Street Address
7. City
8. State (2-letter code)
9. ZIP Code

OPTIONAL FIELDS (offer after required):
- Email
- Address Line 2
- Insurance Provider
- Insurance Member ID
- Preferred Language
- Emergency Contact Name
- Emergency Contact Phone

CONVERSATION FLOW:
1. Start: "Hello! Welcome to our clinic. I'm here to help you register as a new patient. Can I start by getting your first name?"
2. Ask fields one at a time naturally
3. If invalid data: "I need a valid [field]. Could you please provide [field] again?"
4. Before saving, confirm all required fields back to the caller and get a yes
5. Call the save_patient tool ONLY after every required field has been collected
   and the caller explicitly confirms the complete registration summary
6. On success: "You're all set, [First Name]! Thank you for registering."
7. On error: relay the error message you got back and ask the caller to correct that field

SPEAKING PACE:
- If the caller asks you to speak slower, faster, or back to normal, call the
  set_speaking_pace tool with "slow", "fast", or "normal" BEFORE your next reply,
  and keep that pace for the rest of the call unless asked to change again.

VALIDATION:
- Phone: exactly 10 digits
- DOB: MM/DD/YYYY, not in the future
- State: valid 2-letter US abbreviation
- ZIP: 5 or 9 digits
- Names: letters, hyphens, apostrophes only

TONE: Warm, professional, conversational - like a real person, not a robot."""

_PACE_TO_SPEED = {"slow": 0.8, "normal": 1.0, "fast": 1.15}


def log_tool_call_safely(db, **kwargs) -> None:
    try:
        crud.create_tool_call_log(db, **kwargs)
    except Exception as log_error:
        logger.warning("Dashboard tool-call log failed: %s", log_error)


def log_pipeline_metric_safely(db, **kwargs) -> None:
    try:
        crud.create_pipeline_metric(db, **kwargs)
    except Exception as log_error:
        logger.warning("Dashboard pipeline metric log failed: %s", log_error)


def dashboard_write(label: str, writer) -> None:
    db = SessionLocal()
    try:
        writer(db)
    except Exception as error:
        logger.warning("Dashboard %s write failed: %s", label, error)
    finally:
        db.close()


def seconds_to_ms(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value) * 1000)
    except (TypeError, ValueError):
        return None


def metric_payload(metrics: Any) -> dict[str, Any]:
    if hasattr(metrics, "model_dump"):
        return clean_json(metrics.model_dump(mode="json"))
    if isinstance(metrics, dict):
        return clean_json(metrics)
    return {"type": type(metrics).__name__, "repr": repr(metrics)}


def clean_json(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    return value


def metric_stage(metrics_type: str) -> str:
    return {
        "stt_metrics": "stt",
        "llm_metrics": "llm",
        "tts_metrics": "tts",
        "vad_metrics": "vad",
        "eou_metrics": "vad",
        "eot_inference_metrics": "vad",
        "realtime_model_metrics": "llm",
        "interruption_metrics": "turn_detection",
        "avatar_metrics": "output",
    }.get(metrics_type, metrics_type.replace("_metrics", "") or "unknown")


def text_from_chat_item(item: Any) -> str:
    text = getattr(item, "text_content", None) or getattr(item, "raw_text_content", None)
    if callable(text):
        text = text()
    if isinstance(text, list):
        text = " ".join(str(part) for part in text if part)
    return str(text or "").strip()


class IntakeAgent(Agent):
    def __init__(self, *, call_id: Optional[str] = None, current_patient_id: Optional[dict[str, Optional[str]]] = None) -> None:
        self.call_id = call_id
        self.current_patient_id = current_patient_id if current_patient_id is not None else {"value": None}
        super().__init__(
            instructions=INSTRUCTIONS,
            stt=deepgram.STT(model="nova-2", language="en"),
            llm=groq.LLM(model=GROQ_MODEL),
            tts=elevenlabs.TTS(voice_id=ELEVENLABS_VOICE_ID, api_key=os.getenv("ELEVENLABS_API_KEY")),
            vad=silero.VAD.load(),
        )

    @function_tool
    async def save_patient(
        self,
        first_name: str,
        last_name: str,
        date_of_birth: str,
        sex: str,
        phone_number: str,
        address_line_1: str,
        city: str,
        state: str,
        zip_code: str,
        email: Optional[str] = None,
        address_line_2: Optional[str] = None,
        insurance_provider: Optional[str] = None,
        insurance_member_id: Optional[str] = None,
        preferred_language: Optional[str] = None,
        emergency_contact_name: Optional[str] = None,
        emergency_contact_phone: Optional[str] = None,
    ) -> str:
        """Save the collected patient demographic information to the database.

        Call this only after all required fields are known and the caller has
        explicitly confirmed the complete registration summary.
        date_of_birth should be given in MM/DD/YYYY format as spoken by the caller.
        """
        raw_args = {
            "first_name": first_name,
            "last_name": last_name,
            "date_of_birth": date_of_birth,
            "sex": sex,
            "phone_number": phone_number,
            "address_line_1": address_line_1,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "email": email,
            "address_line_2": address_line_2,
            "insurance_provider": insurance_provider,
            "insurance_member_id": insurance_member_id,
            "preferred_language": preferred_language,
            "emergency_contact_name": emergency_contact_name,
            "emergency_contact_phone": emergency_contact_phone,
        }
        raw_args = {k: v for k, v in raw_args.items() if v is not None}
        started_at = time.perf_counter()

        db = SessionLocal()
        args = dict(raw_args)
        try:
            args = schemas.normalize_patient_args(raw_args)
            logger.info("Final collected patient payload: %s", args)
            existing = crud.get_patient_by_phone(db, args.get("phone_number", ""))
            if existing:
                logger.warning("Duplicate phone on save_patient: %s", args.get("phone_number"))
                result = f"A patient with phone {args['phone_number']} already exists."
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                log_tool_call_safely(
                    db,
                    tool_name="save_patient",
                    arguments=args,
                    result_text=result,
                    success=False,
                    call_id=self.call_id,
                    patient_id=existing.patient_id,
                    latency_ms=latency_ms,
                )
                log_pipeline_metric_safely(
                    db,
                    stage="database",
                    provider="postgres",
                    latency_ms=latency_ms,
                    status="duplicate",
                    payload={"tool": "save_patient"},
                    call_id=self.call_id,
                    patient_id=existing.patient_id,
                )
                return result

            patient_data = schemas.PatientCreate(**args)
            new_patient = crud.create_patient(db, patient_data)
            self.current_patient_id["value"] = new_patient.patient_id
            logger.info("Patient saved: %s %s (%s)", new_patient.first_name, new_patient.last_name, new_patient.patient_id)
            result = f"Patient {new_patient.first_name} {new_patient.last_name} registered successfully."
            if self.call_id:
                crud.update_call_session(
                    db,
                    self.call_id,
                    patient_id=new_patient.patient_id,
                    status="completed",
                    final_payload=args,
                    summary=result,
                )
            log_tool_call_safely(
                db,
                tool_name="save_patient",
                arguments=args,
                result_text=result,
                success=True,
                call_id=self.call_id,
                patient_id=new_patient.patient_id,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
            )
            log_pipeline_metric_safely(
                db,
                stage="database",
                provider="postgres",
                latency_ms=int((time.perf_counter() - started_at) * 1000),
                status="ok",
                payload={"tool": "save_patient"},
                call_id=self.call_id,
                patient_id=new_patient.patient_id,
            )
            return result
        except (ValueError, ValidationError) as ve:
            logger.error("Validation error saving patient: %s; raw_args=%s", ve, raw_args)
            result = (
                "That information could not be saved yet: "
                f"{ve}. Please ask the caller for the missing or corrected field, "
                "then confirm the complete registration summary before saving."
            )
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            log_tool_call_safely(
                db,
                tool_name="save_patient",
                arguments=args,
                result_text=result,
                success=False,
                call_id=self.call_id,
                latency_ms=latency_ms,
            )
            log_pipeline_metric_safely(
                db,
                stage="database",
                provider="postgres",
                latency_ms=latency_ms,
                status="validation_error",
                payload={"tool": "save_patient", "error": str(ve)},
                call_id=self.call_id,
                patient_id=self.current_patient_id["value"],
            )
            return result
        except Exception as e:
            logger.exception("Database error saving patient")
            result = "Sorry, I could not save that registration because the database write failed. Please try again."
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            log_tool_call_safely(
                db,
                tool_name="save_patient",
                arguments=args,
                result_text=str(e),
                success=False,
                call_id=self.call_id,
                latency_ms=latency_ms,
            )
            log_pipeline_metric_safely(
                db,
                stage="database",
                provider="postgres",
                latency_ms=latency_ms,
                status="error",
                payload={"tool": "save_patient", "error": str(e)},
                call_id=self.call_id,
                patient_id=self.current_patient_id["value"],
            )
            return result
        finally:
            db.close()

    @function_tool
    async def check_duplicate_patient(self, phone_number: str) -> str:
        """Check whether a patient with this phone number already exists."""
        started_at = time.perf_counter()
        db = SessionLocal()
        try:
            digits = "".join(c for c in phone_number if c.isdigit())[-10:]
            existing = crud.get_patient_by_phone(db, digits)
            result = "A patient with that phone number already exists." if existing else "No existing patient found with that phone number."
            log_tool_call_safely(
                db,
                tool_name="check_duplicate_patient",
                arguments={"phone_number": digits},
                result_text=result,
                success=True,
                call_id=self.call_id,
                patient_id=existing.patient_id if existing else None,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
            )
            return result
        finally:
            db.close()

    @function_tool
    async def set_speaking_pace(self, pace: str) -> str:
        """Adjust speaking speed. pace must be one of: slow, normal, fast."""
        speed = _PACE_TO_SPEED.get(pace.lower().strip(), 1.0)
        try:
            await self.session.tts.update_options(voice_settings={"speed": speed})
        except AttributeError:
            logger.warning("Installed elevenlabs plugin has no update_options(); pace change skipped.")
            return "Sorry, I can't change my speaking pace right now."
        logger.info("Speaking pace set to %s (speed=%s)", pace, speed)
        return f"Okay, speaking at a {pace} pace now."


async def entrypoint(ctx: agents.JobContext) -> None:
    init_database()
    call_id = getattr(getattr(ctx, "job", None), "id", None) or str(uuid.uuid4())
    room_name = getattr(ctx.room, "name", "unknown")
    current_patient_id: dict[str, Optional[str]] = {"value": None}
    logger.info(
        "LiveKit job received: room=%s job=%s",
        room_name,
        call_id,
    )
    logger.info("Database initialized for LiveKit worker: %s", safe_database_url())

    def _upsert_call_start(db) -> None:
        existing = crud.get_call(db, call_id)
        if existing:
            crud.update_call_session(
                db,
                call_id,
                livekit_room_name=room_name,
                status="started",
                error_message="",
            )
        else:
            crud.create_call_session(
                db,
                call_id=call_id,
                livekit_room_name=room_name,
                status="started",
            )

    dashboard_write("call start", _upsert_call_start)
    await ctx.connect()

    try:
        participant = await asyncio.wait_for(ctx.wait_for_participant(), timeout=2)
        attributes = getattr(participant, "attributes", {}) or {}
        caller_phone = (
            attributes.get("sip.phoneNumber")
            or attributes.get("sip.trunkPhoneNumber")
            or attributes.get("lk.phoneNumber")
        )
        dashboard_write(
            "caller identity",
            lambda db: crud.update_call_session(
                db,
                call_id,
                livekit_participant_identity=getattr(participant, "identity", None),
                caller_phone=caller_phone,
            ),
        )
    except asyncio.TimeoutError:
        logger.info("No remote caller participant available yet for dashboard metadata.")

    session = AgentSession(user_away_timeout=None, transcription_timeout=5.0)
    close_future = asyncio.get_running_loop().create_future()

    def _persist_state_event(event_type: str, event) -> None:
        dashboard_write(
            event_type,
            lambda db: crud.create_agent_event(
                db,
                call_id=call_id,
                patient_id=current_patient_id["value"],
                event_type=event_type,
                payload={
                    "old_state": getattr(event, "old_state", None),
                    "new_state": getattr(event, "new_state", None),
                },
            ),
        )

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(event) -> None:
        logger.info(
            "User transcript: final=%s text=%r",
            event.is_final,
            event.transcript,
        )
        if event.transcript:
            dashboard_write(
                "user transcript",
                lambda db: crud.create_transcript_message(
                    db,
                    call_id=call_id,
                    patient_id=current_patient_id["value"],
                    speaker="patient",
                    text=event.transcript,
                    is_final=event.is_final,
                ),
            )

    @session.on("user_transcription_timeout")
    def _on_user_transcription_timeout(event) -> None:
        logger.warning(
            "User speech detected but no transcript: speech_duration=%.2f",
            event.speech_duration,
        )
        dashboard_write(
            "transcription timeout",
            lambda db: crud.create_agent_event(
                db,
                call_id=call_id,
                patient_id=current_patient_id["value"],
                event_type="user_transcription_timeout",
                provider="deepgram",
                payload={"speech_duration": event.speech_duration},
            ),
        )
        session.say(
            "I heard something, but I couldn't make out the words. Could you please repeat that?",
            allow_interruptions=True,
        )

    @session.on("agent_state_changed")
    def _on_agent_state_changed(event) -> None:
        logger.info("Agent state changed: %s -> %s", event.old_state, event.new_state)
        _persist_state_event("agent_state_changed", event)

    @session.on("user_state_changed")
    def _on_user_state_changed(event) -> None:
        logger.info("User state changed: %s -> %s", event.old_state, event.new_state)
        _persist_state_event("user_state_changed", event)

    @session.on("conversation_item_added")
    def _on_conversation_item_added(event) -> None:
        item = event.item
        role = getattr(item, "role", "")
        text = text_from_chat_item(item)
        if role == "assistant" and text:
            dashboard_write(
                "assistant transcript",
                lambda db: crud.create_transcript_message(
                    db,
                    call_id=call_id,
                    patient_id=current_patient_id["value"],
                    speaker="agent",
                    text=text,
                    is_final=True,
                ),
            )

    @session.on("metrics_collected")
    def _on_metrics_collected(event) -> None:
        payload = metric_payload(event.metrics)
        metrics_type = payload.get("type", "unknown_metrics")
        metadata = payload.get("metadata") or {}
        provider = metadata.get("model_provider") or payload.get("label")
        model = metadata.get("model_name")
        latency_seconds = next(
            (
                payload.get(key)
                for key in (
                    "duration",
                    "ttft",
                    "ttfb",
                    "end_of_utterance_delay",
                    "transcription_delay",
                    "inference_duration_total",
                    "total_duration",
                )
                if payload.get(key) not in (None, -1)
            ),
            None,
        )
        duration_seconds = payload.get("audio_duration") or payload.get("duration")

        def _write_metrics(db) -> None:
            crud.create_pipeline_metric(
                db,
                call_id=call_id,
                patient_id=current_patient_id["value"],
                stage=metric_stage(metrics_type),
                provider=provider,
                model=model,
                latency_ms=seconds_to_ms(latency_seconds),
                duration_ms=seconds_to_ms(duration_seconds),
                status="ok",
                payload=payload,
            )
            if metrics_type in {"llm_metrics", "realtime_model_metrics"}:
                crud.create_llm_token_usage(
                    db,
                    call_id=call_id,
                    patient_id=current_patient_id["value"],
                    provider=provider or "llm",
                    model=model or GROQ_MODEL,
                    prompt_tokens=int(payload.get("prompt_tokens") or payload.get("input_tokens") or 0),
                    completion_tokens=int(
                        payload.get("completion_tokens") or payload.get("output_tokens") or 0
                    ),
                    total_tokens=int(payload.get("total_tokens") or 0),
                    latency_ms=seconds_to_ms(payload.get("duration")),
                )

        dashboard_write("pipeline metric", _write_metrics)

    @session.on("error")
    def _on_session_error(event) -> None:
        logger.error("Agent session error from %r: %r", event.source, event.error)
        dashboard_write(
            "session error",
            lambda db: crud.create_agent_event(
                db,
                call_id=call_id,
                patient_id=current_patient_id["value"],
                event_type="session_error",
                provider=repr(event.source),
                payload={"error": repr(event.error)},
            ),
        )

    @session.on("close")
    def _on_session_close(event) -> None:
        logger.info("Agent session closed: reason=%s error=%r", event.reason, event.error)

        def _finish_call(db) -> None:
            call = crud.get_call(db, call_id)
            if call and call.status == "completed":
                status = "completed"
            elif getattr(event, "error", None):
                status = "failed"
            else:
                status = "dropped"
            crud.finish_call_session(
                db,
                call_id,
                status=status,
                error_message=repr(event.error) if getattr(event, "error", None) else None,
            )

        dashboard_write("call finish", _finish_call)
        if not close_future.done():
            close_future.set_result(None)

    await session.start(
        agent=IntakeAgent(call_id=call_id, current_patient_id=current_patient_id),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    logger.info("Agent session started: room=%s", getattr(ctx.room, "name", "unknown"))
    greeting = session.say(
        "Hello! Welcome to our clinic. I'm here to help you register as a new patient. "
        "Can I start by getting your first name?",
        allow_interruptions=True,
    )
    await close_future


if __name__ == "__main__":
    init_database()
    logger.info("Database initialized for LiveKit worker: %s", safe_database_url())
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="patient-intake-agent",
            job_executor_type=agents.JobExecutorType.THREAD,
            num_idle_processes=0,
        )
    )
