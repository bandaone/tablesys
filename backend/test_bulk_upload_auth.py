import requests

# 1. Login to get token
login_data = {
    "username": "coord",
    "password": "password"
}
res = requests.post("http://localhost:8000/api/auth/login", json=login_data)

if res.status_code != 200:
    print("Login failed!", res.status_code, res.text)
    print("Trying form data login...")
    res = requests.post("http://localhost:8000/api/auth/login", data=login_data)
    
if res.status_code == 200:
    token = res.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Test Courses Bulk Upload
    files = {'file': ('test.csv', b'code,name,level,credits,lecture_hours,department_code\nC2,Test2,2,3,2,CEE\n', 'text/csv')}
    res_upload = requests.post("http://localhost:8000/api/courses/bulk-upload", files=files, headers=headers)
    print("Courses Upload Response:", res_upload.status_code, res_upload.text)
    
    # 3. Test Rooms Bulk Upload
    files2 = {'file': ('rooms.csv', b'name,building,capacity,room_type\nRoom 101,Engineering Block,50,lecture_hall\n', 'text/csv')}
    res_upload2 = requests.post("http://localhost:8000/api/rooms/bulk-upload", files=files2, headers=headers)
    print("Rooms Upload Response:", res_upload2.status_code, res_upload2.text)
else:
    print("Could not get token:", res.text)
