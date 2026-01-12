"""
Security and Authentication Tests for TABLESYS
Run this to verify login security and functionality
"""
import requests
from datetime import datetime

API_BASE = "http://localhost:8000/api"
REQUEST_TIMEOUT = 10  # seconds

def print_test(name, status, message=""):
    status_icon = "✅" if status else "❌"
    print(f"{status_icon} {name}")
    if message:
        print(f"   {message}")

def test_login_valid_users():
    """Test login with valid users"""
    print("\n" + "="*60)
    print("TEST 1: Valid User Login")
    print("="*60)
    
    valid_users = ['coordinator', 'admin', 'AEN', 'MEC', 'EEE', 'CEE', 'GEE']
    
    for username in valid_users:
        try:
            response = requests.post(
                f"{API_BASE}/auth/login",
                json={"username": username},
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get('access_token')
                print_test(f"Login as '{username}'", True, f"Token: {token[:20]}...")
                
                # Test /me endpoint
                me_response = requests.get(
                    f"{API_BASE}/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=REQUEST_TIMEOUT
                )
                
                if me_response.status_code == 200:
                    user_data = me_response.json()
                    print_test(
                        "  Get user info", 
                        True, 
                        f"Role: {user_data['role']}, Name: {user_data['full_name']}"
                    )
                else:
                    print_test(
                        "  Get user info", 
                        False, 
                        f"Status: {me_response.status_code}"
                    )
            else:
                print_test(f"Login as '{username}'", False, 
                         f"Status: {response.status_code}, Error: {response.text}")
        except Exception as e:
            print_test(f"Login as '{username}'", False, f"Error: {str(e)}")

def test_login_invalid_users():
    """Test login with invalid users"""
    print("\n" + "="*60)
    print("TEST 2: Invalid User Login (Should Fail)")
    print("="*60)
    
    invalid_users = ['hacker', 'admin123', '', 'DROP TABLE users;', '<script>alert()</script>']
    
    for username in invalid_users:
        try:
            response = requests.post(
                f"{API_BASE}/auth/login",
                json={"username": username},
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 401:
                print_test(f"Reject '{username}'", True, "Correctly rejected")
            else:
                print_test(f"Reject '{username}'", False, 
                         f"Unexpected status: {response.status_code}")
        except Exception as e:
            print_test(f"Reject '{username}'", False, f"Error: {str(e)}")

def test_case_insensitive_login():
    """Test case-insensitive login"""
    print("\n" + "="*60)
    print("TEST 3: Case-Insensitive Login")
    print("="*60)
    
    test_cases = [
        ('coordinator', 'coordinator'),
        ('COORDINATOR', 'coordinator'),
        ('CoOrDiNaToR', 'coordinator'),
        ('aen', 'AEN'),
        ('AEN', 'AEN'),
        ('mec', 'MEC'),
    ]
    
    for input_username, expected_username in test_cases:
        try:
            response = requests.post(
                f"{API_BASE}/auth/login",
                json={"username": input_username},
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                token = response.json()['access_token']
                me_response = requests.get(
                    f"{API_BASE}/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=REQUEST_TIMEOUT
                )
                actual_username = me_response.json()['username']
                
                if actual_username == expected_username:
                    print_test(f"'{input_username}' → '{actual_username}'", True)
                else:
                    print_test(f"'{input_username}' → '{actual_username}'", False,
                             f"Expected '{expected_username}'")
            else:
                print_test(f"'{input_username}'", False, 
                         f"Login failed: {response.status_code}")
        except Exception as e:
            print_test(f"'{input_username}'", False, f"Error: {str(e)}")

def test_token_expiry():
    """Test token validation"""
    print("\n" + "="*60)
    print("TEST 4: Token Validation")
    print("="*60)
    
    # Test with valid token
    response = requests.post(
        f"{API_BASE}/auth/login",
        json={"username": "coordinator"},
        timeout=REQUEST_TIMEOUT
    )
    if response.status_code == 200:
        token = response.json()['access_token']
        
        # Test valid token
        me_response = requests.get(
            f"{API_BASE}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT
        )
        print_test("Valid token accepted", me_response.status_code == 200)
        
        # Test invalid token
        me_response = requests.get(
            f"{API_BASE}/auth/me",
            headers={"Authorization": "Bearer invalid_token_12345"},
            timeout=REQUEST_TIMEOUT
        )
        print_test("Invalid token rejected", me_response.status_code == 401)
        
        # Test no token
        me_response = requests.get(
            f"{API_BASE}/auth/me",
            timeout=REQUEST_TIMEOUT
        )
        print_test("No token rejected", me_response.status_code == 401)
    else:
        print_test("Token validation", False, "Could not get initial token")

def test_role_based_access():
    """Test role-based permissions"""
    print("\n" + "="*60)
    print("TEST 5: Role-Based Access Control")
    print("="*60)
    
    # Login as coordinator
    coord_response = requests.post(
        f"{API_BASE}/auth/login",
        json={"username": "coordinator"},
        timeout=REQUEST_TIMEOUT
    )
    coord_token = coord_response.json()['access_token']
    
    # Login as HOD
    hod_response = requests.post(
        f"{API_BASE}/auth/login",
        json={"username": "AEN"},
        timeout=REQUEST_TIMEOUT
    )
    hod_token = hod_response.json()['access_token']
    
    # Test coordinator access
    me_response = requests.get(
        f"{API_BASE}/auth/me",
        headers={"Authorization": f"Bearer {coord_token}"},
        timeout=REQUEST_TIMEOUT
    )
    user_data = me_response.json()
    print_test("Coordinator role", user_data['role'] == 'coordinator')
    
    # Test HOD access
    me_response = requests.get(
        f"{API_BASE}/auth/me",
        headers={"Authorization": f"Bearer {hod_token}"},
        timeout=REQUEST_TIMEOUT
    )
    user_data = me_response.json()
    print_test("HOD role", user_data['role'] == 'hod')

def test_cors_headers():
    """Test CORS configuration"""
    print("\n" + "="*60)
    print("TEST 6: CORS Configuration")
    print("="*60)
    
    try:
        response = requests.options(
            f"{API_BASE}/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            },
            timeout=REQUEST_TIMEOUT
        )
        
        cors_allowed = response.headers.get("Access-Control-Allow-Origin")
        print_test("CORS headers present", cors_allowed is not None, 
                  f"Origin: {cors_allowed}")
    except Exception as e:
        print_test("CORS check", False, f"Error: {str(e)}")

if __name__ == "__main__":
    print("\n" + "🔒 " + "="*58 + " 🔒")
    print("   TABLESYS SECURITY & AUTHENTICATION TEST SUITE")
    print("🔒 " + "="*58 + " 🔒")
    print(f"Testing API at: {API_BASE}")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Check if API is running
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is running\n")
        else:
            print("⚠️  API responded but might not be healthy\n")
    except Exception as e:
        print(f"❌ Cannot connect to API: {str(e)}")
        print("\n💡 Make sure the backend is running:")
        print("   cd backend")
        print("   uvicorn app.main:app --reload")
        exit(1)
    
    # Run tests
    test_login_valid_users()
    test_login_invalid_users()
    test_case_insensitive_login()
    test_token_expiry()
    test_role_based_access()
    test_cors_headers()
    
    print("\n" + "="*60)
    print("✅ TEST SUITE COMPLETED")
    print("="*60)
    print("\n💡 SECURITY RECOMMENDATIONS:")
    print("   1. Change SECRET_KEY in production (.env file)")
    print("   2. Use HTTPS in production")
    print("   3. Consider adding rate limiting for login endpoint")
    print("   4. Enable database backups")
    print("   5. Monitor failed login attempts")
    print("\n")
