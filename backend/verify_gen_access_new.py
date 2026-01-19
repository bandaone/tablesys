
import requests
import sys

BASE_URL = "http://localhost:8000"

def test_login(username, password="password"):
    print(f"Testing login for user: {username}")
    try:
        # Note: The seeding script uses "pass" as the password, but just in case check seed_users.py
        # Checking seed_users.py line 63: hashed_password=get_password_hash("pass")
        # So password is "pass"
        response = requests.post(f"{BASE_URL}/api/auth/login", data={"username": username, "password": password}, timeout=10)
        
        if response.status_code == 200:
            token = response.json()["access_token"]
            print("[+] Login successful. Token obtained.")
            
            # Verify user details
            headers = {"Authorization": f"Bearer {token}"}
            me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=10)
            
            if me_response.status_code == 200:
                user_data = me_response.json()
                print(f"[+] User details: {user_data}")
                
                if user_data['username'] == 'hod_gen' and user_data['role'] == 'hod' and user_data['department_id'] == 0:
                     print("[+] VERIFICATION PASSED: User is hod_gen, role is hod, dept is 0 (General)")
                     return True
                else:
                    print("[-] VERIFICATION FAILED: User details mismatch.")
                    return False
            else:
                print(f"[-] Failed to get user details: {me_response.status_code} {me_response.text}")
                return False
        else:
            print(f"[-] Login failed: {response.status_code} {response.text}")
            return False
            
    except Exception as e:
        print(f"[-] Error: {e}")
        return False

if __name__ == "__main__":
    if test_login("hod_gen"):
        sys.exit(0)
    else:
        sys.exit(1)
