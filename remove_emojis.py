import os

with open('AGENT_STATUS.md', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('✅ ', '')
content = content.replace('⏳ ', '')
content = content.replace('🔧 ', '')

with open('AGENT_STATUS.md', 'w', encoding='utf-8') as f:
    f.write(content)

print("Removed emojis.")