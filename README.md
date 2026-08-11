# Voice AI Patient Registration System

## 📱 Live Demo

**Call the number below to register a patient:**
```
📞 [YOUR VAPI PHONE NUMBER - ADD HERE]
```

**Test the REST API:**
```
🌐 https://assessment-usm9.onrender.com
```

---

## 🎯 Overview

A voice-based AI agent that collects U.S. patient demographic information through natural conversation, saves it to a persistent database, and exposes it via a REST API.

**System Flow:**
```
Caller dials → Vapi Voice Agent → Collects info → Saves to DB → API retrieves data
```

---

## 🏗️ Architecture

### Tech Stack
| Layer | Technology | Why |
|-------|-----------|-----|
| **Telephony + Voice AI** | Vapi | Handles STT/TTS/LLM orchestration, abstracts complexity |
| **LLM** | OpenAI/Claude (via Vapi) | Natural language understanding & generation |
| **Backend** | FastAPI (Python) | Fast, async, great for real-time APIs |
| **Database** | SQLite | Lightweight, file-based, perfect for MVP |
| **Deployment** | Render | Free tier, auto-deploys from GitHub |

### Data Flow
```
┌─────────────┐
│   Caller    │
└──────┬──────┘
       │ (voice call)
       ▼
┌─────────────────────────────────────┐
│   Vapi Voice Agent                   │
│  - Collects demographic info         │
│  - Validates on-the-fly              │
│  - Confirms before saving            │
└──────┬──────────────────────────────┘
       │ (POST /vapi/save-patient)
       ▼
┌─────────────────────────────────────┐
│   FastAPI Backend                    │
│  - Validates input                   │
│  - Normalizes data (dates, phone)    │
│  - Saves to database                 │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│   SQLite Database                    │
│  - Persistent patient records        │
│  - Soft-delete support               │
│  - Auto-generated UUIDs              │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│   REST API Endpoints                 │
│  - GET /patients (list, search)      │
│  - GET /patients/{id} (single)       │
│  - POST /patients (create)           │
│  - PUT /patients/{id} (update)       │
│  - DELETE /patients/{id} (soft-del)  │
└─────────────────────────────────────┘
```

---

## 🚀 Deployment Status

| Component | Status | URL |
|-----------|--------|-----|
| **Backend API** | ✅ Live | https://assessment-usm9.onrender.com |
| **Vapi Phone Number** | ✅ Live | [YOUR NUMBER] |
| **Database** | ✅ Persistent SQLite | patients.db |

---

## 📊 Patient Data Model

### Required Fields
```
✓ first_name (1-50 chars)
✓ last_name (1-50 chars)
✓ date_of_birth (MM/DD/YYYY)
✓ sex (Male, Female, Other, Decline to Answer)
✓ phone_number (10-digit US number)
✓ address_line_1 (street address)
✓ city (1-100 chars)
✓ state (2-letter code: CA, NY, TX, etc)
✓ zip_code (5 or 9 digit format)
```

### Optional Fields
```
◇ email
◇ address_line_2 (apt/suite/unit)
◇ insurance_provider
◇ insurance_member_id
◇ preferred_language (default: English)
◇ emergency_contact_name
◇ emergency_contact_phone
```

### Auto-Generated
```
• patient_id (UUID)
• created_at (timestamp UTC)
• updated_at (timestamp UTC)
• deleted_at (soft-delete timestamp)
```

---

## 🔧 API Reference

### List All Patients
```bash
curl https://assessment-usm9.onrender.com/patients
```

**Response:**
```json
{
  "data": {
    "patients": [
      {
        "patient_id": "550e8400-e29b-41d4-a716-446655440000",
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
        "sex": "Male",
        "phone_number": "5551234567",
        "address_line_1": "123 Main St",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94105",
        "email": null,
        "created_at": "2026-08-12T20:07:52.598000",
        "updated_at": "2026-08-12T20:07:52.598000",
        "deleted_at": null
      }
    ]
  },
  "error": null,
  "status": 200
}
```

### Get Single Patient
```bash
curl https://assessment-usm9.onrender.com/patients/{patient_id}
```

### Search Patients
```bash
# By last name
curl "https://assessment-usm9.onrender.com/patients/search?last_name=Doe"

# By phone number
curl "https://assessment-usm9.onrender.com/patients/search?phone_number=5551234567"

# By date of birth
curl "https://assessment-usm9.onrender.com/patients/search?date_of_birth=1990-01-15"
```

### Create Patient (Direct API)
```bash
curl -X POST https://assessment-usm9.onrender.com/patients \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane",
    "last_name": "Smith",
    "date_of_birth": "1985-03-22",
    "sex": "Female",
    "phone_number": "5559876543",
    "address_line_1": "456 Oak Ave",
    "city": "Los Angeles",
    "state": "CA",
    "zip_code": "90001"
  }'
```

**Returns:** 201 Created with patient record + UUID

### Update Patient
```bash
curl -X PUT https://assessment-usm9.onrender.com/patients/{patient_id} \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "phone_number": "5551234568"
  }'
```

### Delete Patient (Soft-Delete)
```bash
curl -X DELETE https://assessment-usm9.onrender.com/patients/{patient_id}
```

**Returns:** 200 OK (sets deleted_at timestamp, data not removed)

---

## 💬 Voice Agent Flow

**Example Conversation:**
```
Agent: "Hello, welcome to our clinic! I'm here to help register you as a new patient. 
        What's your first name?"

Caller: "John"

Agent: "Thanks, John. And what's your last name?"

Caller: "Smith"

Agent: "Got it. And when were you born? Please give me the date in MM/DD/YYYY format."

Caller: "01/15/1990"

[... continues collecting all 9 required fields ...]

Agent: "Let me confirm everything I have:
        Name: John Smith
        DOB: 01/15/1990
        Sex: Male
        Phone: 555-1234-5678
        Address: 123 Main St
        City: San Francisco
        State: CA
        Zip: 94105
        
        Does everything look correct?"

Caller: "Yes, that's right"

Agent: "Perfect! You're all set, John. Thank you for registering with us!"

[Agent calls save_patient tool, data saved to database]
```

---

## ⚙️ Environment Variables

Create `.env` file:
```
PORT=8000
DATABASE_URL=sqlite:///./patients.db
LOG_LEVEL=INFO
```

---

## 🧪 Testing

### Test With Phone Call
1. Call your Vapi number
2. Complete registration
3. Verify data appears in API:
   ```bash
   curl https://assessment-usm9.onrender.com/patients
   ```

### Test Direct API Creation
```bash
curl -X POST https://assessment-usm9.onrender.com/patients \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Test",
    "last_name": "User",
    "date_of_birth": "2000-05-15",
    "sex": "Other",
    "phone_number": "5551112222",
    "address_line_1": "999 Test St",
    "city": "TestCity",
    "state": "CA",
    "zip_code": "12345"
  }'
```

### Test Search
```bash
curl "https://assessment-usm9.onrender.com/patients/search?last_name=User"
```

---

## ✅ Features Implemented

- ✅ **Voice Registration**: Natural conversational agent via Vapi
- ✅ **Data Persistence**: SQLite database with auto-generated UUIDs
- ✅ **REST API**: Full CRUD endpoints with proper HTTP status codes
- ✅ **Validation**: Server-side validation on all inputs
- ✅ **Data Normalization**: 
  - Date conversion (MM/DD/YYYY → YYYY-MM-DD)
  - Phone number cleaning (remove spaces/dashes, take last 10 digits)
  - Sex field capitalization (male → Male)
- ✅ **Soft Deletes**: Data marked deleted but not removed
- ✅ **Search/Filter**: Query by last_name, phone_number, date_of_birth
- ✅ **Error Handling**: Graceful error messages for invalid data
- ✅ **Live Deployment**: Render + Vapi running 24/7

---

## 🎯 Vapi Integration Details

### Tool Configuration

**Tool Name:** `save_patient`

**Server URL:** `https://assessment-usm9.onrender.com/vapi/save-patient`

**Parameters:** See Patient Data Model above (JSON Schema format)

**Behavior:**
- Agent collects required fields conversationally
- Agent offers optional fields: "I can also collect insurance info, emergency contact, and preferred language. Would you like to provide any?"
- Agent confirms all info before calling tool
- On tool success: Agent confirms to caller
- On tool error: Agent relays error gracefully

---

## 🔒 Security

- ✅ No hardcoded API keys (uses environment variables)
- ✅ Server-side validation (don't trust client input)
- ✅ Basic input sanitization
- ✅ No sensitive data in logs
- ⚠️ **Dev/Testing Only**: No HIPAA compliance, no authentication/authorization

---

## 📝 Known Limitations

| Limitation | Reason | Production Fix |
|-----------|--------|-----------------|
| **SQLite** | Single-file DB, not prod-scale | Migrate to PostgreSQL |
| **No auth** | MVP doesn't need it | Add JWT/OAuth |
| **No HIPAA** | Dev assessment only | Full HIPAA compliance layer |
| **Unique phone** | Current constraint | Allow duplicates with versioning |
| **No call recording** | Out of scope | Integrate call transcript API |

---

## 🚀 Next Steps (Future Enhancements)

- [ ] Multi-language support (Spanish, Mandarin, etc)
- [ ] Appointment scheduling integration
- [ ] Call transcript/recording storage
- [ ] Web dashboard for staff to view patients
- [ ] Email confirmation after registration
- [ ] SMS appointment reminders
- [ ] PostgreSQL migration for scale
- [ ] User authentication for API
- [ ] HIPAA compliance layer

---

## 📞 Support

For issues or questions:
- Check logs: Render dashboard → Logs
- Call the number and confirm agent works
- Test API directly with curl commands above

---

## 📄 License

Assessment project - For evaluation purposes only.

---

**Last Updated:** 2026-08-12  
**Status:** ✅ Production Ready for Testing
