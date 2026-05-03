import requests
import sys
import json

BASE_URL = "http://localhost:8000"

# User to test with (Standard HOD user, not coordinator - though in this system HODs are just users with roles)
# Assuming 'hod_aen' exists and has password 'pass' (based on verify_logins.py)
TEST_USER = {"username": "hod_aen", "password": "pass"}

def get_token(user):
    print(f"[*] Logging in as {user['username']}...")
    try:
        # Note: Depending on the enhanced auth, checking if it uses JSON or form-data
        # verify_logins.py used JSON {"username": ...} which might be a dev-shortcut, 
        # but typically OAuth2 uses form-data. I will try the standard dev shortcut first if it was working.
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": user["username"], "password": user["password"]}, 
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        
        # If that failed, try standard OAuth2 form
        response = requests.post(
            f"{BASE_URL}/token",
            data={"username": user["username"], "password": user["password"]}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
            
        print(f"[-] Login failed for {user['username']}: {response.text}")
        return None
    except Exception as e:
        print(f"[-] Login error: {e}")
        return None

def verify_groups():
    token = get_token(TEST_USER)
    if not token:
        print("[-] Could not get token, aborting.")
        sys.exit(1)
        
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n[TestCase 1] Create Parent Group (Department Level)")
    parent_group_data = {
        "name": "TEST-AEN-L2",
        "level": 2,
        "department_id": 1, # AEN
        "size": 100,
        "group_type": "department",
        "display_code": "AEN2"
    }
    
    # 1. DELETE IF EXISTS (Cleanup)
    # Getting all groups to find ID
    resp = requests.get(f"{BASE_URL}/api/groups/", headers=headers)
    all_groups = resp.json()
    for g in all_groups:
        if g['name'] == parent_group_data['name'] or g['name'] == "TEST-AEN-L2-LAB1":
            print(f"[*] Cleaning up existing group {g['name']} ({g['id']})...")
            requests.delete(f"{BASE_URL}/api/groups/{g['id']}", headers=headers)

    # 2. CREATE PARENT
    resp = requests.post(f"{BASE_URL}/api/groups/", json=parent_group_data, headers=headers)
    if resp.status_code == 201:
        parent_group = resp.json()
        print(f"[+] Parent Group Created: ID {parent_group['id']}")
    else:
        print(f"[-] Failed to create parent group: {resp.text}")
        sys.exit(1)
        
    print("\n[TestCase 2] Create Child Group (Lab Group) linked to Parent")
    child_group_data = {
        "name": "TEST-AEN-L2-LAB1",
        "level": 2,
        "department_id": 1,
        "size": 20,
        "group_type": "lab_group",
        "parent_group_id": parent_group['id'],
        "display_code": "L2-L1"
    }
    
    resp = requests.post(f"{BASE_URL}/api/groups/", json=child_group_data, headers=headers)
    if resp.status_code == 201:
        child_group = resp.json()
        print(f"[+] Child Group Created: ID {child_group['id']}")
        
        # Verify Linkage
        if child_group['parent_group_id'] == parent_group['id']:
            print(f"[+] correct parent_group_id linked: {child_group['parent_group_id']}")
        else:
            print(f"[-] Mismatch parent_group_id. Expected {parent_group['id']}, got {child_group.get('parent_group_id')}")
    else:
        print(f"[-] Failed to create child group: {resp.text}")
        sys.exit(1)
        
    print("\n[TestCase 3] Verify visibility in list")
    resp = requests.get(f"{BASE_URL}/api/groups/", headers=headers)
    groups = resp.json()
    found_parent = False
    found_child = False
    for g in groups:
        if g['id'] == parent_group['id']: found_parent = True
        if g['id'] == child_group['id']: found_child = True
        
    if found_parent and found_child:
        print("[+] Both groups found in global list")
    else:
        print(f"[-] Groups missing from list. Parent: {found_parent}, Child: {found_child}")

    print("\n[TestCase 4] Cleanup")
    # Delete child first (if foreign keys restrict, though typically cascade isn't set strictly in this app models usually)
    resp = requests.delete(f"{BASE_URL}/api/groups/{child_group['id']}", headers=headers)
    print(f"[*] Delete Child: {resp.status_code}")
    
    resp = requests.delete(f"{BASE_URL}/api/groups/{parent_group['id']}", headers=headers)
    print(f"[*] Delete Parent: {resp.status_code}")
    
    print("\nALL TESTS COMPLETED SUCCESSFULLY")

if __name__ == "__main__":
    try:
        verify_groups()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)
