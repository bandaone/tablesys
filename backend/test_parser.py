import sys
import os
sys.path.append("/home/on3/DENNIS/TABLESYS/backend")

from app.utils.template_parser import StructuralTemplateParser
import pandas as pd

import tempfile

with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
    f.write(",CS Year 3 AI,CS Year 3 ML\n")
    f.write("08:00,Lecture,Lecture\n")
    tmp = f.name

parser = StructuralTemplateParser(tmp, "csv")
try:
    res = parser.parse()
    for c in res['containers']:
        print("Group parsed as:", c['group_label'])
finally:
    os.unlink(tmp)
