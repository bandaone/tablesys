import re

courses = [
  {"code": 'MEC 3001', "title": 'Mechanical Engineering Drawing II'},
  {"code": 'MEC 3351', "title": 'Strength of Materials I'},
  {"code": 'ENG 3165', "title": 'Fluid Mechanics & Thermodynamics'},
  {"code": 'MAT 3110', "title": 'Engineering Mathematics II'},
  {"code": 'MEC 4105', "title": 'Production Technology I'}
]

def test_match(groupCode, groupName):
    alias = (groupCode or groupName or '').upper()
    cleanAlias = re.sub(r'[^A-Z0-9]', '', alias)
    print(f"\nTesting: groupCode='{groupCode}', groupName='{groupName}' -> cleanAlias='{cleanAlias}'")
    
    if not cleanAlias:
        print("Empty clean alias, maps nothing.")
        return
        
    for c in courses:
        codeUpper = c['code'].upper()
        cleanCodeUpper = re.sub(r'[^A-Z0-9]', '', codeUpper)
        isMatch = (alias in codeUpper) or (cleanAlias in cleanCodeUpper)
        if isMatch:
            print(f"  [MATCH] {c['code']}")

test_match('MEC-3', 'Mechanical Engineering Yr3')
test_match(None, 'Mechanical Engineering Yr3')
test_match(None, 'Mechanical Engineering')
