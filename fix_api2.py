import os, re
count = 0
for root, dirs, files in os.walk(r'backend\tests'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            new_content = re.sub(r'\"/api/(?!v1/)', '\"/api/v1/', content)
            if content != new_content:
                with open(path, 'w', encoding='utf-8') as file:
                    file.write(new_content)
                count += 1
print(f'Updated {count} files')
