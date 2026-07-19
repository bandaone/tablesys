import re

with open('frontend/src/pages/UsersPage.tsx', 'r') as f:
    content = f.read()

content = content.replace(
"""  useEffect(() => {
    const canManageUsers = isCoordinator || isTenantAdmin;
    if (canManageUsers) {""",
"""  const canManageUsers = isCoordinator || isTenantAdmin;
  useEffect(() => {
    if (canManageUsers) {"""
)

with open('frontend/src/pages/UsersPage.tsx', 'w') as f:
    f.write(content)
