import urllib.request, urllib.parse, json

data = urllib.parse.urlencode({"username": "admin", "password": "password123"}).encode("utf-8")
req = urllib.request.Request("http://localhost:8000/api/v1/auth/login", data=data)
try:
    res = urllib.request.urlopen(req)
    token = json.loads(res.read())["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    req2 = urllib.request.Request("http://localhost:8000/api/v1/notifications/", headers=headers)
    res2 = urllib.request.urlopen(req2)
    print("GET /notifications/ response:")
    print(res2.read().decode())
except Exception as e:
    print("Error:", e)
