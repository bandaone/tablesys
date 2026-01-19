
import requests
import json
import sys

BASE_URL = "http://localhost:3002/api"
LOGIN_URL = f"{BASE_URL}/auth/login"
ROOMS_URL = f"{BASE_URL}/rooms/"

def login(username, password):
    response = requests.post(LOGIN_URL, json={"username": username, "password": password})
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Login failed: {response.text}")
        sys.exit(1)

def create_room(token, name):
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "name": name,
        "building": "Test Block",
        "capacity": 50,
        "room_type": "lecture_hall",
        "equipment": ["Projector"],
        "priority": "standard"
    }
    response = requests.post(ROOMS_URL, json=data, headers=headers)
    if response.status_code == 201:
        return response.json()["id"]
    else:
        print(f"Failed to create room: {response.text}")
        return None

def delete_room(token, room_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.delete(f"{ROOMS_URL}{room_id}", headers=headers)
    return response.status_code == 204

def delete_all_rooms(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.delete(ROOMS_URL, headers=headers)
    return response.status_code == 200

def run_verification():
    print("Logging in as coordinator...")
    token = login("coordinator", "password123")
    
    # 1. Test Individual Deletion
    print("\n--- Testing Individual Deletion ---")
    room_id = create_room(token, "TestRoom101")
    if room_id:
        print(f"Created room TestRoom101 with ID {room_id}")
        if delete_room(token, room_id):
            print("Successfully deleted room TestRoom101")
        else:
            print("Failed to delete room TestRoom101")
    
    # 2. Test Bulk Deletion
    print("\n--- Testing Bulk Deletion ---")
    ids = []
    for i in range(3):
        rid = create_room(token, f"BulkRoom{i}")
        if rid: ids.append(rid)
    print(f"Created {len(ids)} rooms for bulk delete test")
    
    if delete_all_rooms(token):
        print("Successfully requested delete all rooms")
        # Verify count is 0
        headers = {"Authorization": f"Bearer {token}"}
        rooms = requests.get(ROOMS_URL, headers=headers).json()
        if len(rooms) == 0:
            print("Verified: Room count is 0")
        else:
            print(f"Failed: Room count is {len(rooms)}")
    else:
        print("Failed to delete all rooms")

if __name__ == "__main__":
    run_verification()
