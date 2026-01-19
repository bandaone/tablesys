
import requests
import sys

BASE_URL = "http://localhost:8000"

USERS = [
    {"username": "coordinator", "password": "pass"},
    {"username": "hod_aen", "password": "pass"},
    {"username": "hod_cee", "password": "pass"},
    {"username": "hod_eee", "password": "pass"},
    {"username": "hod_gee", "password": "pass"},
    {"username": "hod_mec", "password": "pass"},
]

def verify_login():
    print(f"[*] Verifying logins against {BASE_URL}...")
    
    success_count = 0
    for user in USERS:
        try:
            # Login endpoint is /api/auth/login and expects JSON body with just username
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"username": user["username"]},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                print(f"[+] Login successful: {user['username']}")
                success_count += 1
            else:
                print(f"[-] Login failed: {user['username']} - Status: {response.status_code}")
                print(f"    Response: {response.text}")

        except Exception as e:
            print(f"[-] Error testing {user['username']}: {e}")

    print(f"\nResults: {success_count}/{len(USERS)} passed.")
    
    if success_count == len(USERS):
        print("ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    verify_login()
