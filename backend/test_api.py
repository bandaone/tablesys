import urllib.request
import urllib.parse
import json

data = urllib.parse.urlencode({"username": "superadmin", "password": "T4sN9kQ2vH7mD1xP8cL3wR6yB0fJ5uZa"}).encode()
req = urllib.request.Request("http://localhost:8000/api/v1/auth/login", data=data)
try:
    token = json.loads(urllib.request.urlopen(req).read())["access_token"]
    req2 = urllib.request.Request("http://localhost:8000/api/v1/lecturers?skip=0&limit=10")
    req2.add_header("Authorization", f"Bearer {token}")
    lecturers = json.loads(urllib.request.urlopen(req2).read())
    for l in lecturers:
        print(f"{l.get('staff_number')} - Assignments:", l.get("assignments"))
except Exception as e:
    print("Error:", e)
