from pydantic import BaseModel, EmailStr, field_validator, Field
from datetime import date, datetime
from typing import Optional

class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    date_of_birth: date
    sex: str  # Male, Female, Other, Decline to Answer
    phone_number: str = Field(..., min_length=10, max_length=10)
    email: Optional[str] = None
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

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        if not v.isdigit():
            raise ValueError('Phone number must contain only digits')
        if len(v) != 10:
            raise ValueError('Phone number must be exactly 10 digits')
        return v

    @field_validator('date_of_birth')
    @classmethod
    def validate_dob(cls, v):
        if v >= date.today():
            raise ValueError('Date of birth cannot be today or in the future')
        return v

    @field_validator('state')
    @classmethod
    def validate_state(cls, v):
        valid_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
        }
        if v.upper() not in valid_states:
            raise ValueError('Invalid state abbreviation')
        return v.upper()

    @field_validator('zip_code')
    @classmethod
    def validate_zip(cls, v):
        v = v.replace('-', '')
        if not v.isdigit():
            raise ValueError('ZIP code must contain only digits')
        if len(v) not in [5, 9]:
            raise ValueError('ZIP code must be 5 or 9 digits')
        return v

    @field_validator('sex')
    @classmethod
    def validate_sex(cls, v):
        valid_options = {'Male', 'Female', 'Other', 'Decline to Answer'}
        if v not in valid_options:
            raise ValueError(f'Sex must be one of {valid_options}')
        return v

class PatientCreate(PatientBase):
    pass

class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
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
