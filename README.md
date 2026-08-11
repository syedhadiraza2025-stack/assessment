# Voice AI Agent - Patient Registration System

A voice-based AI agent accessible via phone that collects patient demographic information through natural conversation, persists data to a database, and exposes it through a REST API.

## System Architecture

```
Phone Call (Caller) 
    ↔ 
Voice AI Agent (Vapi + Groq LLM) 
    ↔ 
Database (SQLite) 
    ↓ 
REST API (FastAPI)
```

## Tech Stack

- **Telephony & Voice AI**: Vapi
- **LLM**: Groq (openai/gpt-oss-120b)
- **Backend**: Python FastAPI
- **Database**: SQLite
- **Hosting**: Render (deployment ready)

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd ai_services/assessment
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the root directory:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
VAPI_PRIVATE_KEY=your_vapi_private_key
DATABASE_URL=sqlite:///./patients.db
PORT=8000
ENVIRONMENT=development
```

**Get API Keys:**
- **Groq API Key**: https://console.groq.com
- **Vapi Private Key**: https://dashboard.vapi.ai/org/api-keys

### 4. Initialize Database
```bash
python -c "from database import engine; from models import Base; Base.metadata.create_all(bind=engine)"
```

### 5. Run the Backend Server
```bash
python main.py
```

Server will start at `http://localhost:8000`

### 6. Test the API
In another terminal:
```bash
python test_api.py
```

## API Endpoints

### Health Check
- **GET** `/health` - Service status

### Patient Management
- **GET** `/patients` - List all patients (paginated)
- **GET** `/patients/{patient_id}` - Get specific patient
- **GET** `/patients/search?last_name=...&date_of_birth=...&phone_number=...` - Search patients
- **POST** `/patients` - Create new patient
- **PUT** `/patients/{patient_id}` - Update patient
- **DELETE** `/patients/{patient_id}` - Soft delete patient

### Duplicate Detection
- **POST** `/patients/{patient_id}/check-duplicate` - Check if patient exists by phone

## Response Format

All API responses follow this format:

```json
{
  "data": { ... },
  "error": null,
  "status": 200
}
```

## Patient Data Model

### Required Fields
- `first_name` (string, 1-50 chars)
- `last_name` (string, 1-50 chars)
- `date_of_birth` (date, not in future)
- `sex` (enum: Male, Female, Other, Decline to Answer)
- `phone_number` (string, 10-digit US format)
- `address_line_1` (string)
- `city` (string, 1-100 chars)
- `state` (string, 2-letter US state abbreviation)
- `zip_code` (string, 5 or 9 digit format)

### Optional Fields
- `email` (string, valid email format)
- `address_line_2` (string)
- `insurance_provider` (string)
- `insurance_member_id` (string)
- `preferred_language` (string, default: English)
- `emergency_contact_name` (string)
- `emergency_contact_phone` (string, 10-digit US format)

### Auto-Generated Fields
- `patient_id` (UUID)
- `created_at` (timestamp)
- `updated_at` (timestamp)
- `deleted_at` (timestamp, null until soft deleted)

## Voice Agent Conversation Flow

1. **Greeting** - Agent welcomes caller and explains purpose
2. **Required Information Collection** - Asks for essential patient details one at a time
3. **Optional Information** - Offers to collect insurance, emergency contact, language preference
4. **Confirmation** - Reads back all collected information
5. **Validation** - If any field is invalid, re-prompts specifically
6. **Save** - Sends data to backend API
7. **Completion** - Confirms successful registration and ends call

## Voice Agent Features

- **Natural Conversation**: LLM-powered, not rigid IVR
- **Error Handling**: Validates data and re-prompts for invalid entries
- **Corrections**: Allows caller to correct information mid-conversation
- **Duplicate Detection**: Recognizes returning callers by phone number
- **Graceful Degradation**: Handles connection drops and timeout scenarios

## Validation Rules

| Field | Rules |
|-------|-------|
| Phone | Must be 10 consecutive digits |
| DOB | Must be a valid date in the past |
| State | Valid 2-letter US state code |
| ZIP Code | 5 or 9 digits |
| Names | Alphabetic, hyphens, apostrophes only |

## Deployment to Render

### 1. Push to GitHub
```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Create Render Service
1. Go to https://render.com
2. Create new Web Service
3. Connect your GitHub repository
4. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Environment**: Add variables from `.env`

### 3. Get Vapi Phone Number
After deployment, create a phone number:
```bash
python -c "
import asyncio
from vapi_integration import create_agent, create_phone_number

async def setup():
    agent = await create_agent()
    phone = await create_phone_number(agent['id'])
    print(f'Phone Number: {phone[\"number\"]}')

asyncio.run(setup())
"
```

## Known Limitations & Trade-offs

1. **SQLite for Production**: Using SQLite for simplicity in 3-hour assessment. For production, use PostgreSQL.
2. **No Call Recording**: Transcripts not stored (can be added via Vapi webhooks)
3. **No Authentication**: API is open (add API key auth for production)
4. **Simple Error Messages**: Error details not exposed (add proper error handling layer)
5. **No Rate Limiting**: Can add via FastAPI middleware if needed
6. **Voice Quality**: Using ElevenLabs "paula" voice (can customize)

## Testing

### Unit Tests (via API)
```bash
python test_api.py
```

### Manual Testing
1. Call the phone number
2. Follow the voice agent prompts
3. Provide patient information
4. Confirm and submit
5. Check API: `curl http://localhost:8000/patients`

## Bonus Features Implemented

- ✅ Duplicate detection by phone number
- ✅ Soft delete (with `deleted_at` timestamp)
- ✅ Search by multiple filters
- ✅ Comprehensive validation
- ✅ Logging for all operations
- ✅ CORS enabled for frontend integration

## Bonus Features Not Yet Implemented

- Appointment scheduling after registration
- Multi-language support
- Call recording/transcript storage
- Web dashboard
- Automated tests (pytest)

## Environment Variables Reference

```env
GROQ_API_KEY          # Groq API key for LLM
GROQ_MODEL            # Groq model name (default: openai/gpt-oss-120b)
VAPI_PRIVATE_KEY      # Vapi private API key
DATABASE_URL          # SQLite connection string
PORT                  # Server port (default: 8000)
ENVIRONMENT           # development or production
```

## Troubleshooting

### Database Issues
- Delete `patients.db` and restart to reinitialize
- Check file permissions if using filesystem database

### Vapi Connection Issues
- Verify API keys are correct
- Check internet connection
- Ensure Vapi account has credits

### Groq LLM Issues
- Verify Groq API key is valid
- Check Groq console for rate limits
- Verify model name is correct

## Architecture Decisions

### Why Vapi?
- Abstracts STT/TTS complexity
- Handles telephony infrastructure
- Fast integration (~1 hour vs building from scratch)
- Supports tool calling for database integration

### Why Groq?
- Fast inference times (best for voice latency)
- Reasonable pricing
- Good model quality for conversational tasks
- Free tier available for testing

### Why FastAPI?
- Minimal setup for REST APIs
- Fast execution
- Built-in validation via Pydantic
- Easy async/await support for Vapi webhooks

### Why SQLite?
- Zero setup/configuration
- File-based, survives restarts
- Good for MVP/assessment
- Easy to migrate to PostgreSQL later

## Next Steps (If More Time)

1. Add appointment scheduling endpoint
2. Implement multi-language support
3. Add call recording via Vapi webhooks
4. Build web dashboard for viewing patients
5. Add pytest unit/integration tests
6. Implement API authentication (API keys)
7. Add rate limiting and request validation
8. Deploy to production (PostgreSQL, proper auth)

## Support

For issues or questions:
1. Check error logs: `tail -f app.log`
2. Test API with curl or Postman
3. Verify environment variables are loaded
4. Check Vapi/Groq dashboards for service status

---

**Built for Voice AI Agent Patient Registration Assessment**
