#!/usr/bin/env python3
"""Simple test runner to capture output"""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "test_solver_scale.py", "-v", "--tb=short"],
    capture_output=True,
    text=True,
    cwd="/app"
)

print(result.stdout)
print(result.stderr)
sys.exit(result.returncode)
