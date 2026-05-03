import asyncio
from httpx import AsyncClient
from app.main import app

async def run():
    async with AsyncClient(app=app, base_url='http://test') as ac:
        l = await ac.post('/api/v1/auth/login', data={'username': 'coordinator', 'password': 'password'})
        h = {'Authorization': f'Bearer {l.json()["access_token"]}'}
        d = await ac.get('/api/v1/departments/', headers=h)
        depts = d.json()
        dept_id = depts[0]['id'] if depts else 1
        
        data = {'name': 'VALIDGRP', 'department_id': dept_id, 'level': 200, 'size': 50}
        res = await ac.post('/api/v1/groups/', json=data, headers=h)
        print('STATUS:', res.status_code)
        print('RESPONSE:', res.text)

asyncio.run(run())
