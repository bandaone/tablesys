import os

with open('frontend/src/pages/SuperAdminPage.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('telemetry?.total_users', 'telemetry?.active_users')
content = content.replace('telemetry?.total_tenants', 'telemetry?.total_universities')
content = content.replace('telemetry?.active_celery_jobs', 'telemetry?.active_solver_jobs')
content = content.replace("telemetry?.redis_alive ? PRIMARY : DANGER", "telemetry?.redis_status === 'online' ? PRIMARY : DANGER")
content = content.replace("telemetry?.redis_alive ? 'ONLINE' : 'CRITICAL'", "telemetry?.redis_status === 'online' ? 'ONLINE' : 'CRITICAL'")
content = content.replace("formatUptime(telemetry?.uptime_seconds)", "telemetry?.system_uptime_hours + 'h'")

with open('frontend/src/pages/SuperAdminPage.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed fields.")