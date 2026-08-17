import asyncio
import os
import random

import httpx


BASE_URL = os.getenv("BASE_URL", "http://localhost:8002")


async def test_api():
    async with httpx.AsyncClient() as client:
        print("Health Check...")
        response = await client.get(f"{BASE_URL}/health")
        print(f"  Status: {response.status_code} - {response.json()}\n")

        print("Creating Patient...")
        phone_number = f"555{random.randint(1000000, 9999999)}"
        patient_data = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1990-05-15",
            "sex": "Male",
            "phone_number": phone_number,
            "email": "john.doe@example.com",
            "address_line_1": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001",
        }
        response = await client.post(f"{BASE_URL}/patients", json=patient_data)
        print(f"  Status: {response.status_code}")
        patient_response = response.json()
        print(f"  Data: {patient_response.get('data')}\n")

        if response.status_code != 201:
            return

        patient_id = patient_response["data"]["patient_id"]

        print(f"Getting Patient {patient_id}...")
        response = await client.get(f"{BASE_URL}/patients/{patient_id}")
        print(f"  Status: {response.status_code}")
        print(f"  Data: {response.json().get('data')}\n")

        print("Listing All Patients...")
        response = await client.get(f"{BASE_URL}/patients")
        print(f"  Status: {response.status_code}")
        print(f"  Count: {len(response.json()['data']['patients'])}\n")

        print("Searching Patient by Phone...")
        response = await client.get(f"{BASE_URL}/patients?phone_number={phone_number}")
        print(f"  Status: {response.status_code}")
        print(f"  Found: {len(response.json()['data']['patients'])} patient(s)\n")

        print(f"Updating Patient {patient_id}...")
        update_data = {"email": "newemail@example.com"}
        response = await client.put(f"{BASE_URL}/patients/{patient_id}", json=update_data)
        print(f"  Status: {response.status_code}")
        print(f"  Updated: {response.json().get('data', {}).get('email')}\n")

        print(f"Deleting Patient {patient_id}...")
        response = await client.delete(f"{BASE_URL}/patients/{patient_id}")
        print(f"  Status: {response.status_code}")
        print(f"  Deleted: {response.json().get('data', {}).get('deleted')}\n")


if __name__ == "__main__":
    print("Testing Patient Registration API...\n")
    asyncio.run(test_api())
    print("All tests completed!")
