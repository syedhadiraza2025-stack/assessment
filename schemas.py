from pydantic import BaseModel, EmailStr, field_validator, Field
from datetime import date, datetime
from typing import Optional
import re

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z'-]*$")
FULL_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z' -]*$")


def validate_person_name(value: str) -> str:
    if not NAME_RE.fullmatch(value):
        raise ValueError("Name must contain only letters, hyphens, and apostrophes")
    return value


def validate_full_name(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    if not FULL_NAME_RE.fullmatch(value):
        raise ValueError("Full name must contain only letters, spaces, hyphens, and apostrophes")
    return value


def validate_us_phone(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    if not value.isdigit():
        raise ValueError("Phone number must contain only digits")
    if len(value) != 10:
        raise ValueError("Phone number must be exactly 10 digits")
    return value


def validate_date_of_birth(value: Optional[date]) -> Optional[date]:
    if value is not None and value >= date.today():
        raise ValueError("Date of birth cannot be today or in the future")
    return value


def validate_state_code(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    valid_states = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
    }
    state = value.upper()
    if state not in valid_states:
        raise ValueError("Invalid state abbreviation")
    return state


def validate_zip_code(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    zip_digits = value.replace("-", "")
    if not zip_digits.isdigit():
        raise ValueError("ZIP code must contain only digits")
    if len(zip_digits) not in [5, 9]:
        raise ValueError("ZIP code must be 5 or 9 digits")
    return zip_digits


def validate_sex_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    normalized = value.strip()
    sex_lower = normalized.lower()
    if sex_lower == "decline to answer":
        normalized = "Decline to Answer"
    elif sex_lower in ("male", "female", "other"):
        normalized = sex_lower.capitalize()
    valid_options = {'Male', 'Female', 'Other', 'Decline to Answer'}
    if normalized not in valid_options:
        raise ValueError(f"Sex must be one of {valid_options}")
    return normalized

class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    date_of_birth: date
    sex: str  # Male, Female, Other, Decline to Answer
    phone_number: str = Field(..., min_length=10, max_length=10)
    email: Optional[EmailStr] = None
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=2)
    zip_code: str
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = "English"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_names(cls, v):
        return validate_person_name(v)

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        return validate_us_phone(v)

    @field_validator('date_of_birth')
    @classmethod
    def validate_dob(cls, v):
        return validate_date_of_birth(v)

    @field_validator('state')
    @classmethod
    def validate_state(cls, v):
        return validate_state_code(v)

    @field_validator('zip_code')
    @classmethod
    def validate_zip(cls, v):
        return validate_zip_code(v)

    @field_validator('sex')
    @classmethod
    def validate_sex(cls, v):
        return validate_sex_value(v)

    @field_validator('emergency_contact_name')
    @classmethod
    def validate_emergency_name(cls, v):
        return validate_full_name(v)

    @field_validator('emergency_contact_phone')
    @classmethod
    def validate_emergency_phone(cls, v):
        return validate_us_phone(v)

class PatientCreate(PatientBase):
    pass

class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_names(cls, v):
        if v is None:
            return v
        return validate_person_name(v)

    @field_validator('phone_number', 'emergency_contact_phone')
    @classmethod
    def validate_phone_fields(cls, v):
        return validate_us_phone(v)

    @field_validator('date_of_birth')
    @classmethod
    def validate_dob(cls, v):
        return validate_date_of_birth(v)

    @field_validator('state')
    @classmethod
    def validate_state(cls, v):
        return validate_state_code(v)

    @field_validator('zip_code')
    @classmethod
    def validate_zip(cls, v):
        return validate_zip_code(v)

    @field_validator('sex')
    @classmethod
    def validate_sex(cls, v):
        return validate_sex_value(v)

    @field_validator('emergency_contact_name')
    @classmethod
    def validate_emergency_name(cls, v):
        return validate_full_name(v)

class PatientResponse(PatientBase):
    patient_id: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class APIResponse(BaseModel):
    data: Optional[dict] = None
    error: Optional[str] = None
    status: int = 200


def normalize_patient_args(args: dict) -> dict:
    """Normalize raw voice-agent tool arguments into PatientCreate-compatible values.

    Handles date format detection (MM/DD/YYYY vs DD/MM/YYYY -> ISO), sex
    capitalization, and phone number digit-cleaning, mirroring what callers
    naturally say on a call rather than what the schema strictly expects.
    """
    normalized = dict(args)

    dob = normalized.get("date_of_birth", "")
    if dob:
        try:
            parts = str(dob).replace("-", "/").split("/")
            if len(parts) == 3:
                first, second, third = int(parts[0]), int(parts[1]), int(parts[2])
                if len(parts[0]) == 4:  # YYYY/MM/DD or YYYY-MM-DD
                    y, m, d = first, second, third
                elif first > 12:  # DD/MM/YYYY
                    d, m, y = first, second, third
                else:  # MM/DD/YYYY
                    m, d, y = first, second, third
                normalized["date_of_birth"] = f"{y}-{m:02d}-{d:02d}"
        except (ValueError, IndexError):
            pass

    if isinstance(normalized.get("sex"), str):
        normalized["sex"] = validate_sex_value(normalized["sex"])

    for phone_field in ("phone_number", "emergency_contact_phone"):
        phone = normalized.get(phone_field)
        if phone:
            digits = "".join(c for c in str(phone) if c.isdigit())
            normalized[phone_field] = digits[-10:] if len(digits) >= 10 else digits

    if normalized.get("zip_code"):
        normalized["zip_code"] = str(normalized["zip_code"]).replace("-", "")

    if isinstance(normalized.get("state"), str):
        normalized["state"] = normalized["state"].upper()

    return normalized
