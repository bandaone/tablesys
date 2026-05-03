import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

async def test():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as ac:
        req = await ac.post('/api/v1/courses/', json={
          'code': 'TEST101', 'name': 'Test Course', 'department_id': 1, 'level': 2,
          'credits': 3, 'lecture_hours': 3, 'tutorial_hours': 1, 'practical_hours': 0,
          'preferred_room_type': 'any', 'course_type': 'department_specific',
          'group_division_type': 'full_group'
        }, headers={'X-University-ID': '1'})
        print(req.status_code, req.text)

asyncio.run(test())
