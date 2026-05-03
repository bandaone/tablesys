import requests

res = requests.post("http://localhost:3002/api/v1/auth/login", 
                    json={"username": "university_admin@tablesys.com", "password": "secure_password"})
print("Auth:", res.status_code)
token = res.json().get("access_token")

if token:
    res2 = requests.get("http://localhost:3002/api/v1/timetables/active/analytics", 
                        headers={"Authorization": f"Bearer {token}"})
    print(f"Status: {res2.status_code}")
    print(res2.json())
