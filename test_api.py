import httpx
import asyncio
from datetime import date

BASE_URL = "http://localhost:8000"

async def test_api():
    async with httpx.AsyncClient() as client:
        # Health check
        print("🏥 Health Check...")
        response = await client.get(f"{BASE_URL}/health")
        print(f"  Status: {response.status_code} - {response.json()}\n")

        # Create patient
        print("📝 Creating Patient...")
        patient_data = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1990-05-15",
            "sex": "Male",
            "phone_number": "5551234567",
            "email": "john.doe@example.com",
            "address_line_1": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001"
        }
        response = await client.post(f"{BASE_URL}/patients", json=patient_data)
        print(f"  Status: {response.status_code}")
        patient_response = response.json()
        print(f"  Data: {patient_response.get('data')}\n")

        if response.status_code == 201:
            patient_id = patient_response['data']['patient_id']

            # Get patient
            print(f"👤 Getting Patient {patient_id}...")
            response = await client.get(f"{BASE_URL}/patients/{patient_id}")
            print(f"  Status: {response.status_code}")
            print(f"  Data: {response.json().get('data')}\n")

            # List patients
            print("📋 Listing All Patients...")
            response = await client.get(f"{BASE_URL}/patients")
            print(f"  Status: {response.status_code}")
            print(f"  Count: {len(response.json()['data']['patients'])}\n")

            # Search patient
            print("🔍 Searching Patient by Phone...")
            response = await client.get(f"{BASE_URL}/patients/search?phone_number=5551234567")
            print(f"  Status: {response.status_code}")
            print(f"  Found: {len(response.json()['data']['patients'])} patient(s)\n")

            # Update patient
            print(f"✏️ Updating Patient {patient_id}...")
            update_data = {"email": "newemail@example.com"}
            response = await client.put(f"{BASE_URL}/patients/{patient_id}", json=update_data)
            print(f"  Status: {response.status_code}")
            print(f"  Updated: {response.json().get('data', {}).get('email')}\n")

            # Delete patient
            print(f"🗑️ Deleting Patient {patient_id}...")
            response = await client.delete(f"{BASE_URL}/patients/{patient_id}")
            print(f"  Status: {response.status_code}")
            print(f"  Deleted: {response.json().get('data', {}).get('deleted')}\n")

if __name__ == "__main__":
    print("🚀 Testing Patient Registration API...\n")
    asyncio.run(test_api())
    print("✅ All tests completed!")
