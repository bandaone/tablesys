from locust import HttpUser, task, between
import random

class CoordinatorUser(HttpUser):
    wait_time = between(1, 5)
    token = None
    
    def on_start(self):
        # We assume the coordinator is pre-seeded in the database
        response = self.client.post("/api/v1/auth/login", data={
            "username": "coordinator@unza.zm",
            "password": "Coord@2024!"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")

    @task(3)
    def view_dashboard(self):
        if self.token:
            self.client.get("/api/v1/dashboard/readiness", headers={"Authorization": f"Bearer {self.token}"})

    @task(2)
    def view_rooms(self):
        if self.token:
            self.client.get("/api/v1/rooms/", headers={"Authorization": f"Bearer {self.token}"})

    @task(2)
    def view_courses(self):
        if self.token:
            self.client.get("/api/v1/courses/", headers={"Authorization": f"Bearer {self.token}"})

    @task(1)
    def trigger_generation(self):
        # In a real heavy load test, we only want a subset of users triggering the engine to avoid instantaneous OOM
        if self.token and random.random() < 0.05: # 5% chance to trigger generation
            payload = {
                "year_level": random.choice(["100", "200", "300", "400"]),
                "semester": 1
            }
            self.client.post("/api/v1/timetables/generate/1/", json=payload, headers={"Authorization": f"Bearer {self.token}"})
