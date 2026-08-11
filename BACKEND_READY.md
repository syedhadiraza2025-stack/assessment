# 🎉 Backend Ready for Testing

## Quick Status

✅ **FastAPI Server**: Running on `http://localhost:8002`  
✅ **Database**: SQLite (`patients.db`)  
✅ **All CRUD Endpoints**: Working  
✅ **Validation**: Active  
✅ **Logging**: Enabled  

## Running the Backend

### Option 1: Simple Start
```bash
cd C:\Users\hadi\Documents\ai_services\assessment
python main.py
```

### Option 2: With Custom Port
```bash
$env:PORT=8002
python main.py
```

## Testing the API

### Health Check
```bash
curl http://localhost:8002/health
```

Response:
```json
{
  "status": "ok",
  "service": "patient-registration-api"
}
```

### Create Patient
```bash
curl -X POST http://localhost:8002/patients \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "1990-05-15",
    "sex": "Male",
    "phone_number": "5551234567",
    "address_line_1": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip_code": "10001"
  }'
```

### List Patients
```bash
curl http://localhost:8002/patients
```

### Get Patient
```bash
curl http://localhost:8002/patients/{patient_id}
```

### Search Patients
```bash
curl "http://localhost:8002/patients/search?last_name=Doe&phone_number=5551234567"
```

### Update Patient
```bash
curl -X PUT http://localhost:8002/patients/{patient_id} \
  -H "Content-Type: application/json" \
  -d '{"email": "newemail@example.com"}'
```

### Delete Patient
```bash
curl -X DELETE http://localhost:8002/patients/{patient_id}
```

## Response Format

All responses follow this format:

```json
{
  "data": { /* object or array */ },
  "error": null,
  "status": 200
}
```

## API Status Codes

- **200** - Success
- **201** - Created
- **400** - Bad Request (validation error)
- **404** - Not Found
- **422** - Unprocessable Entity (duplicate phone)
- **500** - Server Error

## Next Steps: Vapi Integration

To connect the voice AI agent:

1. **Create Vapi Agent** - Use `vapi_integration.py`
2. **Set Webhook URL** - Point to your backend
3. **Create Phone Number** - Get a dialable number
4. **Test Call** - Call the number and speak

### Quick Setup:
```python
import asyncio
from vapi_integration import create_agent, create_phone_number

async def setup():
    # Create agent
    agent = await create_agent(backend_url="http://localhost:8002")
    print(f"Agent ID: {agent['id']}")
    
    # Create phone number
    phone = await create_phone_number(agent['id'])
    print(f"Phone Number: {phone['number']}")

asyncio.run(setup())
```

## Database Schema

- **patients** table with 19 fields
- Auto-generated UUIDs for `patient_id`
- Timestamps: `created_at`, `updated_at`, `deleted_at`
- Validation enforced at model level
- Soft deletes (deleted_at != null)

## Logs

Server logs are printed to stdout. Key events logged:
- Patient creation
- Patient retrieval
- Search operations
- Updates
- Deletions
- Errors

## Validation Rules

| Field | Rules |
|-------|-------|
| phone_number | 10 digits, must be unique |
| date_of_birth | Valid date, not in future |
| state | Valid 2-letter US code |
| zip_code | 5 or 9 digits |
| sex | Male, Female, Other, Decline to Answer |
| name | 1-50 chars, alphabetic + hyphens/apostrophes |

## File Structure

```
assessment/
├── main.py                 # FastAPI app & endpoints
├── models.py              # SQLAlchemy models
├── schemas.py             # Pydantic schemas & validation
├── crud.py                # Database operations
├── database.py            # DB connection & session
├── vapi_integration.py    # Vapi API integration
├── requirements.txt       # Dependencies
├── .env                   # Configuration
├── patients.db            # SQLite database
└── README.md              # Full documentation
```

## Ready for Next Phase

Once Vapi integration is complete:
1. Deploy to Render
2. Create phone number in Vapi
3. Test end-to-end voice flow
4. Verify data persistence

---

**Backend is stable and ready for testing! 🚀**
