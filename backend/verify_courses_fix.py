
import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://localhost:8000"

def test_courses_access(username):
    print(f"Testing courses access for user: {username}")
    try:
        # Login - JSON body
        login_data = json.dumps({"username": username}).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                token = data["access_token"]
                print(f"[+] Login successful.")
                
                # Access courses
                courses_req = urllib.request.Request(f"{BASE_URL}/api/courses/")
                courses_req.add_header("Authorization", f"Bearer {token}")
                
                try:
                    with urllib.request.urlopen(courses_req) as courses_response:
                        if courses_response.status == 200:
                            print(f"[+] Courses access successful. Status: 200 OK")
                            return True
                except urllib.error.HTTPError as e:
                    print(f"[-] Courses access failed: {e.code} {e.reason}")
                    try:
                        print(e.read().decode())
                    except:
                        pass
                    return False
            else:
                print(f"[-] Login failed: {response.status}")
                return False
            
    except Exception as e:
        print(f"[-] Error: {e}")
        try:
            if hasattr(e, 'read'):
                print(e.read().decode())
        except:
            pass
        return False

if __name__ == "__main__":
    if test_courses_access("hod_gen"):
        sys.exit(0)
    else:
        sys.exit(1)
