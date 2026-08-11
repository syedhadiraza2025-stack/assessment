import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, Base, engine
import models

@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    yield SessionLocal()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)

class TestVapiSavePatient:
    """Tests for /vapi/save-patient endpoint"""

    def test_format1_direct_name_and_arguments(self, client, db):
        """Test Vapi payload Format 1: direct name + arguments"""
        payload = {
            "message": {
                "timestamp": 1678901234567,
                "type": "tool-calls",
                "toolCallList": [
                    {
                        "id": "toolu_12345",
                        "name": "save_patient",
                        "arguments": {
                            "first_name": "John",
                            "last_name": "Smith",
                            "date_of_birth": "01/15/1990",
                            "sex": "Male",
                            "phone_number": "4156878288",
                            "address_line_1": "123 Main St",
                            "city": "San Francisco",
                            "state": "CA",
                            "zip_code": "94105"
                        }
                    }
                ]
            }
        }

        response = client.post("/vapi/save-patient", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["toolCallId"] == "toolu_12345"
        assert "result" in data["results"][0]
        assert data["results"][0]["result"] == "Patient saved successfully"

    def test_format2_function_nested(self, client, db):
        """Test Vapi payload Format 2: function.name + function.arguments"""
        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_67890",
                        "function": {
                            "name": "save_patient",
                            "arguments": {
                                "first_name": "Jane",
                                "last_name": "Doe",
                                "date_of_birth": "03/22/1985",
                                "sex": "Female",
                                "phone_number": "5551234567",
                                "address_line_1": "456 Oak Ave",
                                "city": "Los Angeles",
                                "state": "CA",
                                "zip_code": "90001"
                            }
                        }
                    }
                ]
            }
        }

        response = client.post("/vapi/save-patient", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["toolCallId"] == "toolu_67890"
        assert data["results"][0]["result"] == "Patient saved successfully"

    def test_duplicate_phone_number(self, client, db):
        """Test handling of duplicate phone numbers"""
        # Create first patient
        payload1 = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_first",
                        "name": "save_patient",
                        "arguments": {
                            "first_name": "John",
                            "last_name": "Smith",
                            "date_of_birth": "01/15/1990",
                            "sex": "Male",
                            "phone_number": "4156878288",
                            "address_line_1": "123 Main St",
                            "city": "San Francisco",
                            "state": "CA",
                            "zip_code": "94105"
                        }
                    }
                ]
            }
        }
        response1 = client.post("/vapi/save-patient", json=payload1)
        assert response1.status_code == 200

        # Try to create second patient with same phone
        payload2 = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_second",
                        "name": "save_patient",
                        "arguments": {
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "date_of_birth": "03/22/1985",
                            "sex": "Female",
                            "phone_number": "4156878288",
                            "address_line_1": "456 Oak Ave",
                            "city": "Los Angeles",
                            "state": "CA",
                            "zip_code": "90001"
                        }
                    }
                ]
            }
        }
        response2 = client.post("/vapi/save-patient", json=payload2)

        assert response2.status_code == 200
        data = response2.json()
        assert "error" in data["results"][0]
        assert "already exists" in data["results"][0]["error"]

    def test_missing_message(self, client, db):
        """Test error handling for missing message"""
        payload = {"something": "else"}

        response = client.post("/vapi/save-patient", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "error" in data["results"][0]
        assert "missing 'message'" in data["results"][0]["error"]

    def test_empty_tool_call_list(self, client, db):
        """Test error handling for empty toolCallList"""
        payload = {
            "message": {
                "toolCallList": []
            }
        }

        response = client.post("/vapi/save-patient", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "error" in data["results"][0]
        assert "no toolCallList" in data["results"][0]["error"]

    def test_invalid_date_format(self, client, db):
        """Test validation error for invalid date"""
        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_baddate",
                        "name": "save_patient",
                        "arguments": {
                            "first_name": "John",
                            "last_name": "Smith",
                            "date_of_birth": "13/45/2999",  # Invalid date
                            "sex": "Male",
                            "phone_number": "4156878288",
                            "address_line_1": "123 Main St",
                            "city": "San Francisco",
                            "state": "CA",
                            "zip_code": "94105"
                        }
                    }
                ]
            }
        }

        response = client.post("/vapi/save-patient", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "error" in data["results"][0]
        assert data["results"][0]["toolCallId"] == "toolu_baddate"

    def test_invalid_state(self, client, db):
        """Test validation error for invalid state"""
        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_badstate",
                        "name": "save_patient",
                        "arguments": {
                            "first_name": "John",
                            "last_name": "Smith",
                            "date_of_birth": "01/15/1990",
                            "sex": "Male",
                            "phone_number": "4156878288",
                            "address_line_1": "123 Main St",
                            "city": "San Francisco",
                            "state": "XX",  # Invalid state
                            "zip_code": "94105"
                        }
                    }
                ]
            }
        }

        response = client.post("/vapi/save-patient", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "error" in data["results"][0]

    def test_invalid_phone_number(self, client, db):
        """Test validation error for invalid phone"""
        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_badphone",
                        "name": "save_patient",
                        "arguments": {
                            "first_name": "John",
                            "last_name": "Smith",
                            "date_of_birth": "01/15/1990",
                            "sex": "Male",
                            "phone_number": "123",  # Invalid phone (not 10 digits)
                            "address_line_1": "123 Main St",
                            "city": "San Francisco",
                            "state": "CA",
                            "zip_code": "94105"
                        }
                    }
                ]
            }
        }

        response = client.post("/vapi/save-patient", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "error" in data["results"][0]

    def test_missing_required_fields(self, client, db):
        """Test validation error for missing required fields"""
        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_incomplete",
                        "name": "save_patient",
                        "arguments": {
                            "first_name": "John",
                            "last_name": "Smith"
                            # Missing other required fields
                        }
                    }
                ]
            }
        }

        response = client.post("/vapi/save-patient", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "error" in data["results"][0]

    def test_response_format_matches_vapi_spec(self, client, db):
        """Test that response format exactly matches Vapi specification"""
        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_spec_test",
                        "name": "save_patient",
                        "arguments": {
                            "first_name": "John",
                            "last_name": "Smith",
                            "date_of_birth": "01/15/1990",
                            "sex": "Male",
                            "phone_number": "4156878288",
                            "address_line_1": "123 Main St",
                            "city": "San Francisco",
                            "state": "CA",
                            "zip_code": "94105"
                        }
                    }
                ]
            }
        }

        response = client.post("/vapi/save-patient", json=payload)
        data = response.json()

        # Verify response structure
        assert isinstance(data, dict)
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) > 0

        result = data["results"][0]
        assert "toolCallId" in result
        assert result["toolCallId"] == "toolu_spec_test"
        assert "result" in result or "error" in result
        # result/error should be strings, not nested objects
        if "result" in result:
            assert isinstance(result["result"], str)
        if "error" in result:
            assert isinstance(result["error"], str)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
