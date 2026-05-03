import subprocess  
p = subprocess.run([r'C:\SYSTEMS\TABLESYS\.venv\Scripts\python', '-m', 'pytest', 'tests/test_brain.py'], capture_output=True, text=True)  
open('clean_log.txt', 'w').write(p.stdout)  
