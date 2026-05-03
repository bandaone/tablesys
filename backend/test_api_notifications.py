import requests

login_data = {
    "username": "admin",
    "password": "password"
}
res = requests.post("http://backend:8000/api/v1/auth/login", json=login_data)
if res.status_code != 200:
    res = requests.post("http://backend:8000/api/v1/auth/login", data=login_data)

token = res.json().get("access_token")
if token:
    headers = {"Authorization": f"Bearer {token}"}
    res_notif = requests.get("http://backend:8000/api/v1/notifications/", headers=headers, params={"limit": 20})
    print(res_notif.status_code)
    print(res_notif.json())
