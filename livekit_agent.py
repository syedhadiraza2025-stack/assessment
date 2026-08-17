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
import logging
import time
from typing import Optional

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
5. Call the save_patient tool once confirmed
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


class IntakeAgent(Agent):
    def __init__(self) -> None:
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
        args = schemas.normalize_patient_args(raw_args)
        started_at = time.perf_counter()

        db = SessionLocal()
        try:
            logger.info("Final collected patient payload: %s", args)
            existing = crud.get_patient_by_phone(db, args.get("phone_number", ""))
            if existing:
                logger.warning("Duplicate phone on save_patient: %s", args.get("phone_number"))
                result = f"A patient with phone {args['phone_number']} already exists."
                log_tool_call_safely(
                    db,
                    tool_name="save_patient",
                    arguments=args,
                    result_text=result,
                    success=False,
                    patient_id=existing.patient_id,
                    latency_ms=int((time.perf_counter() - started_at) * 1000),
                )
                return result

            patient_data = schemas.PatientCreate(**args)
            new_patient = crud.create_patient(db, patient_data)
            logger.info("Patient saved: %s %s (%s)", new_patient.first_name, new_patient.last_name, new_patient.patient_id)
            result = f"Patient {new_patient.first_name} {new_patient.last_name} registered successfully."
            log_tool_call_safely(
                db,
                tool_name="save_patient",
                arguments=args,
                result_text=result,
                success=True,
                patient_id=new_patient.patient_id,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
            )
            return result
        except (ValueError, ValidationError) as ve:
            logger.error("Validation error saving patient: %s", ve)
            result = f"That information could not be saved: {ve}"
            log_tool_call_safely(
                db,
                tool_name="save_patient",
                arguments=args,
                result_text=result,
                success=False,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
            )
            return result
        except Exception as e:
            logger.exception("Database error saving patient")
            result = "Sorry, I could not save that registration because the database write failed. Please try again."
            log_tool_call_safely(
                db,
                tool_name="save_patient",
                arguments=args,
                result_text=str(e),
                success=False,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
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
    logger.info(
        "LiveKit job received: room=%s job=%s",
        getattr(ctx.room, "name", "unknown"),
        getattr(getattr(ctx, "job", None), "id", "unknown"),
    )
    logger.info("Database initialized for LiveKit worker: %s", safe_database_url())
    await ctx.connect()

    session = AgentSession(user_away_timeout=None, transcription_timeout=5.0)

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(event) -> None:
        logger.info(
            "User transcript: final=%s text=%r",
            event.is_final,
            event.transcript,
        )

    @session.on("user_transcription_timeout")
    def _on_user_transcription_timeout(event) -> None:
        logger.warning(
            "User speech detected but no transcript: speech_duration=%.2f",
            event.speech_duration,
        )
        session.say(
            "I heard something, but I couldn't make out the words. Could you please repeat that?",
            allow_interruptions=True,
        )

    @session.on("agent_state_changed")
    def _on_agent_state_changed(event) -> None:
        logger.info("Agent state changed: %s -> %s", event.old_state, event.new_state)

    @session.on("user_state_changed")
    def _on_user_state_changed(event) -> None:
        logger.info("User state changed: %s -> %s", event.old_state, event.new_state)

    @session.on("error")
    def _on_session_error(event) -> None:
        logger.error("Agent session error from %r: %r", event.source, event.error)

    await session.start(
        agent=IntakeAgent(),
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
    await greeting.wait_for_playout()


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
