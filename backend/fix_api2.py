import re

with open(r'tests\test_api.py', 'r') as f:
    c = f.read()

c = re.sub(r"assert response.status_code in \[200, 201, 400, 409\], f'Status \{response.status_code\}: \{response.text\}', f'Status \{response.status_code\}: \{response.text\}'", "assert response.status_code in [200, 201, 400, 409], f'Status {response.status_code}: {response.text}'", c)

with open(r'tests\test_api.py', 'w') as f:
    f.write(c)
