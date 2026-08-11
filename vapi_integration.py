import httpx
import json
import os
from typing import Optional

VAPI_API_URL = "https://api.vapi.ai"
VAPI_PRIVATE_KEY = os.getenv("VAPI_PRIVATE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """You are a professional patient intake assistant for a healthcare clinic. Your goal is to collect patient registration information through natural, friendly conversation.

REQUIRED FIELDS TO COLLECT:
- First Name
- Last Name
- Date of Birth (MM/DD/YYYY format)
- Sex (Male, Female, Other, Decline to Answer)
- Phone Number (10-digit US format)
- Street Address
- City
- State (2-letter abbreviation)
- ZIP Code (5 or 9 digit format)

OPTIONAL FIELDS (offer after required fields):
- Email
- Address Line 2
- Insurance Provider
- Insurance Member ID
- Preferred Language
- Emergency Contact Name
- Emergency Contact Phone

CONVERSATION GUIDELINES:
1. Start with a warm greeting
2. Ask one field at a time in a natural way
3. If caller provides invalid data:
   - Clarify what's needed (e.g., "I need a 10-digit phone number")
   - Re-ask specifically for that field
4. Handle interruptions gracefully - allow callers to go back/correct
5. Once all required fields are collected, offer optional fields
6. Always confirm all information before saving:
   - Read back each field clearly
   - Ask caller to confirm each one
   - Allow corrections if needed
7. After confirmation, the system will save the data
8. End with a warm "You're all set!" message

VALIDATION RULES:
- Phone: Must be 10 consecutive digits (remove dashes/spaces)
- DOB: Must be in past (not today or future)
- State: Valid 2-letter US state abbreviation
- ZIP: 5 or 9 digits
- Names: Letters, hyphens, apostrophes only

TONE: Professional but warm and conversational. Make the caller feel heard and comfortable."""

TOOLS = [
    {
        "name": "save_patient",
        "description": "Save collected patient demographic information to the database",
        "parameters": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Patient's first name"},
                "last_name": {"type": "string", "description": "Patient's last name"},
                "date_of_birth": {"type": "string", "description": "Date of birth in MM/DD/YYYY format"},
                "sex": {"type": "string", "enum": ["Male", "Female", "Other", "Decline to Answer"]},
                "phone_number": {"type": "string", "description": "10-digit US phone number"},
                "email": {"type": "string", "description": "Email address (optional)"},
                "address_line_1": {"type": "string", "description": "Street address"},
                "address_line_2": {"type": "string", "description": "Apt/Suite/Unit (optional)"},
                "city": {"type": "string", "description": "City"},
                "state": {"type": "string", "description": "2-letter state abbreviation"},
                "zip_code": {"type": "string", "description": "ZIP code (5 or 9 digits)"},
                "insurance_provider": {"type": "string", "description": "Insurance provider name (optional)"},
                "insurance_member_id": {"type": "string", "description": "Insurance member ID (optional)"},
                "preferred_language": {"type": "string", "description": "Preferred language (optional)"},
                "emergency_contact_name": {"type": "string", "description": "Emergency contact name (optional)"},
                "emergency_contact_phone": {"type": "string", "description": "Emergency contact phone (optional)"}
            },
            "required": ["first_name", "last_name", "date_of_birth", "sex", "phone_number", "address_line_1", "city", "state", "zip_code"]
        }
    },
    {
        "name": "check_duplicate_patient",
        "description": "Check if a patient already exists by phone number",
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "10-digit US phone number to check"}
            },
            "required": ["phone_number"]
        }
    }
]

async def create_agent(phone_number: Optional[str] = None, backend_url: str = "http://localhost:8000"):
    """Create a Vapi voice agent for patient registration"""

    headers = {
        "Authorization": f"Bearer {VAPI_PRIVATE_KEY}",
        "Content-Type": "application/json"
    }

    agent_config = {
        "name": "Patient Registration Agent",
        "model": {
            "provider": "groq",
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        },
        "voice": {
            "provider": "elevenlabs",
            "voiceId": "paula"
        },
        "firstMessage": "Hello! Welcome to our clinic. I'm here to help you register as a new patient. Can I start by getting your first name?",
        "endCallMessage": "Thank you for registering with us. You're all set! Have a great day!",
        "endCallPhrases": ["bye", "goodbye", "thank you", "thanks", "talk to you later"],
        "tools": TOOLS,
        "backchannel": {
            "enabled": True
        },
        "analysisPlan": {
            "summaryMessages": [
                {
                    "role": "user",
                    "content": "Summarize the patient registration data collected during this call."
                }
            ]
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VAPI_API_URL}/agent",
                json=agent_config,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Error creating Vapi agent: {str(e)}")
        raise

async def get_agent(agent_id: str):
    """Get agent details"""
    headers = {
        "Authorization": f"Bearer {VAPI_PRIVATE_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{VAPI_API_URL}/agent/{agent_id}",
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Error getting agent: {str(e)}")
        raise

async def create_phone_number(agent_id: str):
    """Create a phone number and link it to the agent"""
    headers = {
        "Authorization": f"Bearer {VAPI_PRIVATE_KEY}",
        "Content-Type": "application/json"
    }

    phone_config = {
        "provider": "twilio",
        "agent_id": agent_id,
        "name": "Patient Registration Line"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VAPI_API_URL}/phone-number",
                json=phone_config,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Error creating phone number: {str(e)}")
        raise

def get_system_prompt():
    """Get the system prompt for documentation"""
    return SYSTEM_PROMPT

def get_tools_config():
    """Get tools configuration"""
    return TOOLS
