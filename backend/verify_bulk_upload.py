import urllib.request
import urllib.parse
import urllib.error
import json
import sys
import mimetypes

BASE_URL = "http://127.0.0.1:8000/api"
LOGIN_URL = f"{BASE_URL}/auth/login"
UPLOAD_URL = f"{BASE_URL}/rooms/bulk-upload"
ROOMS_URL = f"{BASE_URL}/rooms/"

def login(username, password="pass"):
    data = json.dumps({"username": username, "password": password}).encode('utf-8')
    req = urllib.request.Request(LOGIN_URL, data=data, headers={
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0'
    })
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                result = json.loads(response.read().decode('utf-8'))
                return result["access_token"]
    except urllib.error.HTTPError as e:
        print(f"Login failed for {username}: {e.code} - {e.read().decode()}")
        sys.exit(1)

def encode_multipart_formdata(fields, files):
    boundary = '---Boundary' + '7MA4YWxkTrZu0gW'
    body = []

    for key, value in fields.items():
        body.append(f'--{boundary}'.encode('utf-8'))
        body.append(f'Content-Disposition: form-data; name="{key}"'.encode('utf-8'))
        body.append(b'')
        body.append(str(value).encode('utf-8'))

    for key, (filename, content) in files.items():
        if filename.endswith('.csv'):
            mime_type = 'text/csv'
        else:
            mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        body.append(f'--{boundary}'.encode('utf-8'))
        body.append(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"'.encode('utf-8'))
        body.append(f'Content-Type: {mime_type}'.encode('utf-8'))
        body.append(b'')
        body.append(content)

    body.append(f'--{boundary}--'.encode('utf-8'))
    body.append(b'')
    
    content_type = f'multipart/form-data; boundary={boundary}'
    return b'\r\n'.join(body), content_type

def verify_bulk_upload():
    # Login as coordinator
    token = login("coordinator")
    
    # Upload CSV
    print("Uploading rooms_sample_v2.csv...")
    try:
        with open('rooms_sample_v2.csv', 'rb') as f:
            file_content = f.read()
        
        data, content_type = encode_multipart_formdata({}, {'file': ('rooms_sample_v2.csv', file_content)})
        
        req = urllib.request.Request(UPLOAD_URL, data=data, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type
        })
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("Upload successful:", result)

    except urllib.error.HTTPError as e:
        print(f"Upload failed: {e.code} - {e.read().decode()}")
        sys.exit(1)

    # Verify Rooms
    print("\nVerifying uploaded rooms...")
    req = urllib.request.Request(ROOMS_URL, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    })
    try:
        with urllib.request.urlopen(req) as response:
            rooms = json.loads(response.read().decode('utf-8'))
            for room in rooms:
                priority = room.get('priority')
                equipment = room.get('equipment')
                furn_type = room.get('furniture_type')
                
                print(f"Name: {room['name']}")
                print(f"  Priority: {priority}")
                print(f"  Equipment: {equipment}")
                print(f"  Type: {furn_type}")
                
                # Specific assertions
                if room['name'] == "Lecture Theater 1":
                    if priority != "high":
                        print("  FAIL: Should be high priority")
                    if "Mic" not in (equipment or []):
                        print("  FAIL: Missing Mic")
                    else:
                        print("  PASS: Lecture Theater 1 verified")
                    
    except urllib.error.HTTPError as e:
        print(f"Failed to fetch rooms: {e.code} - {e.read().decode()}")

if __name__ == "__main__":
    verify_bulk_upload()
