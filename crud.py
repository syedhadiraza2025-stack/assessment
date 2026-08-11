from sqlalchemy.orm import Session
from sqlalchemy import and_
from models import Patient
from schemas import PatientCreate, PatientUpdate
from datetime import date
from typing import List, Optional

def create_patient(db: Session, patient: PatientCreate) -> Patient:
    """Create a new patient record"""
    db_patient = Patient(**patient.model_dump())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient

def get_patient(db: Session, patient_id: str) -> Optional[Patient]:
    """Get a patient by ID"""
    return db.query(Patient).filter(
        and_(Patient.patient_id == patient_id, Patient.deleted_at.is_(None))
    ).first()

def get_all_patients(db: Session, skip: int = 0, limit: int = 100) -> List[Patient]:
    """Get all non-deleted patients"""
    return db.query(Patient).filter(
        Patient.deleted_at.is_(None)
    ).offset(skip).limit(limit).all()

def search_patients(
    db: Session,
    last_name: Optional[str] = None,
    date_of_birth: Optional[date] = None,
    phone_number: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Patient]:
    """Search patients by optional filters"""
    query = db.query(Patient).filter(Patient.deleted_at.is_(None))

    if last_name:
        query = query.filter(Patient.last_name.ilike(f"%{last_name}%"))
    if date_of_birth:
        query = query.filter(Patient.date_of_birth == date_of_birth)
    if phone_number:
        query = query.filter(Patient.phone_number == phone_number)

    return query.offset(skip).limit(limit).all()

def update_patient(db: Session, patient_id: str, patient_update: PatientUpdate) -> Optional[Patient]:
    """Update an existing patient"""
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        return None

    update_data = patient_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_patient, key, value)

    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient

def delete_patient(db: Session, patient_id: str) -> bool:
    """Soft delete a patient (set deleted_at timestamp)"""
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        return False

    from datetime import datetime
    db_patient.deleted_at = datetime.utcnow()
    db.add(db_patient)
    db.commit()
    return True

def get_patient_by_phone(db: Session, phone_number: str) -> Optional[Patient]:
    """Get a patient by phone number (for duplicate detection)"""
    return db.query(Patient).filter(
        and_(Patient.phone_number == phone_number, Patient.deleted_at.is_(None))
    ).first()
