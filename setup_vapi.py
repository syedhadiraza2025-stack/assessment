#!/usr/bin/env python3
"""
Setup script to create and configure Vapi voice AI agent
Run this once to provision the phone number and agent
"""

import asyncio
import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

VAPI_API_URL = "https://api.vapi.ai"
VAPI_PRIVATE_KEY = os.getenv("VAPI_PRIVATE_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "https://assessment-usm9.onrender.com")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """You are a professional patient intake assistant for a healthcare clinic. Your goal is to collect patient registration information through natural, friendly conversation.

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
4. After all required fields: "Before I save this, let me confirm all your information..."
5. Read back all fields for confirmation
6. If caller says "yes" or confirms: Save via API
7. On success: "You're all set, [First Name]! Thank you for registering."
8. On error: "I apologize, there was a technical issue. Can you please call back?"

VALIDATION:
- Phone: Must be exactly 10 digits
- DOB: Must be MM/DD/YYYY format and not in future
- State: Valid 2-letter US abbreviation
- ZIP: 5 or 9 digits only
- Names: Letters, hyphens, apostrophes only

TONE: Warm, professional, conversational - like a real person, not a robot."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_patient",
            "description": "Save the collected patient information to the database",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "date_of_birth": {"type": "string", "description": "MM/DD/YYYY format"},
                    "sex": {"type": "string", "enum": ["Male", "Female", "Other", "Decline to Answer"]},
                    "phone_number": {"type": "string"},
                    "email": {"type": "string"},
                    "address_line_1": {"type": "string"},
                    "address_line_2": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "zip_code": {"type": "string"},
                    "insurance_provider": {"type": "string"},
                    "insurance_member_id": {"type": "string"},
                    "preferred_language": {"type": "string"},
                    "emergency_contact_name": {"type": "string"},
                    "emergency_contact_phone": {"type": "string"}
                },
                "required": ["first_name", "last_name", "date_of_birth", "sex", "phone_number",
                           "address_line_1", "city", "state", "zip_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_existing_patient",
            "description": "Check if a patient with this phone number already exists",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {"type": "string"}
                },
                "required": ["phone_number"]
            }
        }
    }
]

async def create_agent():
    """Create the Vapi voice agent"""

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
            "max_tokens": 500
        },
        "voice": {
            "provider": "elevenlabs",
            "voiceId": "paula",
            "speed": 1.0
        },
        "firstMessage": "Hello! Welcome to our clinic. I'm here to help you register as a new patient. Can I start by getting your first name?",
        "endCallMessage": "Thank you for registering with us. You're all set!",
        "endCallPhrases": ["bye", "goodbye", "thank you", "thanks", "okay thanks"],
        "tools": TOOLS,
        "toolDelayMs": 0,
        "backgroundSound": "office",
        "backchannel": {
            "enabled": True
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en"
        }
    }

    print("🔧 Creating Vapi Agent...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VAPI_API_URL}/agent",
                json=agent_config,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            agent = response.json()
            print(f"✅ Agent Created!")
            print(f"   Agent ID: {agent['id']}")
            return agent
    except Exception as e:
        print(f"❌ Error creating agent: {str(e)}")
        raise

async def create_phone_number(agent_id):
    """Create a phone number and link to agent"""

    headers = {
        "Authorization": f"Bearer {VAPI_PRIVATE_KEY}",
        "Content-Type": "application/json"
    }

    phone_config = {
        "provider": "twilio",
        "assistantId": agent_id,
        "name": "Patient Registration Line",
        "numberE164Format": False,
        "areaCode": "415"
    }

    print("\n📞 Provisioning Phone Number...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VAPI_API_URL}/phone-number",
                json=phone_config,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            phone = response.json()
            print(f"✅ Phone Number Created!")
            print(f"   Number: {phone.get('number', 'N/A')}")
            print(f"   Phone ID: {phone.get('id', 'N/A')}")
            return phone
    except Exception as e:
        print(f"❌ Error creating phone number: {str(e)}")
        raise

async def main():
    """Main setup function"""
    print("=" * 60)
    print("🚀 VAPI VOICE AGENT SETUP")
    print("=" * 60)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"LLM: Groq ({GROQ_MODEL})")
    print(f"Voice Provider: ElevenLabs")
    print("=" * 60 + "\n")

    try:
        # Create agent
        agent = await create_agent()
        agent_id = agent['id']

        # Create phone number
        phone = await create_phone_number(agent_id)
        phone_number = phone.get('number', 'N/A')

        # Save config
        config = {
            "agent_id": agent_id,
            "phone_number": phone_number,
            "backend_url": BACKEND_URL,
            "created_at": str(__import__('datetime').datetime.now())
        }

        with open("vapi_config.json", "w") as f:
            json.dump(config, f, indent=2)

        print("\n" + "=" * 60)
        print("✅ SETUP COMPLETE!")
        print("=" * 60)
        print(f"\n📱 PHONE NUMBER TO CALL: {phone_number}")
        print(f"\n🔑 Agent ID: {agent_id}")
        print(f"🔗 Backend: {BACKEND_URL}")
        print(f"\n💾 Config saved to: vapi_config.json")
        print("\n" + "=" * 60)
        print("NEXT STEPS:")
        print("1. Save the phone number above")
        print("2. Call the number to test")
        print("3. Speak naturally to register a patient")
        print("4. Check the API to verify data was saved")
        print("\nTest API:")
        print(f"  curl {BACKEND_URL}/patients")
        print("=" * 60 + "\n")

        return config

    except Exception as e:
        print(f"\n❌ Setup failed: {str(e)}")
        print("Check your Vapi API key and try again.")
        return None

if __name__ == "__main__":
    config = asyncio.run(main())
