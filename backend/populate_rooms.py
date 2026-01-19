
import requests

BASE_URL = "http://localhost:3002/api"
LOGIN_URL = f"{BASE_URL}/auth/login"
ROOMS_URL = f"{BASE_URL}/rooms/"

def login(username, password):
    response = requests.post(LOGIN_URL, json={"username": username, "password": password})
    return response.json()["access_token"]

def populate():
    token = login("coordinator", "password123")
    headers = {"Authorization": f"Bearer {token}"}
    
    for i in range(5):
        data = {
            "name": f"UI-Test-Room-{i}",
            "building": "Engineering UI",
            "capacity": 30 + i*10,
            "room_type": "lecture_hall",
            "equipment": ["Projector" if i % 2 == 0 else "Whiteboard"],
            "priority": "standard"
        }
        requests.post(ROOMS_URL, json=data, headers=headers)
    print("Populated 5 rooms")

if __name__ == "__main__":
    populate()
