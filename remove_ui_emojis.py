import os

def remove_emojis_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replacing emojis
    content = content.replace('👤', '')
    content = content.replace('📍', '')
    content = content.replace('✅', '')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

remove_emojis_from_file('frontend/src/pages/DashboardPage.tsx')
remove_emojis_from_file('frontend/src/pages/LecturersPage.tsx')

print("Removed UI Emojis")
