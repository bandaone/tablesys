import urllib.request, urllib.parse, json
data = urllib.parse.urlencode({"username": "coordinator", "password": "password123"}).encode("utf-8")
req = urllib.request.Request("http://localhost:8000/api/v1/auth/login", data=data)
try:
    res = urllib.request.urlopen(req)
    token = json.loads(res.read())["access_token"]
    req2 = urllib.request.Request("http://localhost:8000/api/v1/notifications/", headers={"Authorization": f"Bearer {token}"})
    print(json.dumps(json.loads(urllib.request.urlopen(req2).read()), indent=2))
except Exception as e:
    print("Error:", e)
