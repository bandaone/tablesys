import requests

def run():
    r = requests.post('http://127.0.0.1:8000/api/v1/auth/login', json={'username': 'admin', 'password': 'change-me'})
    if r.status_code != 200:
        print("Login failed!", r.text)
        # Try coordinator
        r = requests.post('http://127.0.0.1:8000/api/v1/auth/login', json={'username': 'coordinator', 'password': 'change-me'})
        if r.status_code != 200:
             print("Login failed 2!", r.text)
             return

    token = r.json().get('access_token')
    headers = {'Authorization': f'Bearer {token}'}

    print("--- Testing Notifications ---")
    r0 = requests.post('http://127.0.0.1:8000/api/v1/notifications/test', headers=headers)
    print("Create test notif:", r0.status_code, r0.text)

    r1 = requests.get('http://127.0.0.1:8000/api/v1/notifications/unread-count', headers=headers)
    print("Unread Count:", r1.status_code, r1.text)

    r2 = requests.get('http://127.0.0.1:8000/api/v1/notifications', headers=headers)
    print("Get Notifications:", r2.status_code, r2.text[:300])

    r3 = requests.post('http://127.0.0.1:8000/api/v1/notifications/mark-all-read', headers=headers)
    print("Mark All Read:", r3.status_code, r3.text)

run()
