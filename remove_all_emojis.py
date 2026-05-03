import os
import re

with open('AGENT_STATUS.md', 'r', encoding='utf-8') as f:
    content = f.read()

emojis = set()
for char in content:
    if ord(char) > 127:
        if char not in ['—', '…', '‘', '’', '“', '”', '∞']:
            emojis.add(char)

print(f"Non-ASCII found: {emojis}")

for e in emojis:
    content = content.replace(e, '')

with open('AGENT_STATUS.md', 'w', encoding='utf-8') as f:
    f.write(content)

print("Removed all non-ascii characters (excluding typography).")
