const courses = [
  { code: 'MEC 3001', title: 'Mechanical Engineering Drawing II' },
  { code: 'MEC 3351', title: 'Strength of Materials I' },
  { code: 'ENG 3165', title: 'Fluid Mechanics & Thermodynamics' },
  { code: 'MAT 3110', title: 'Engineering Mathematics II' },
  { code: 'MEC 4105', title: 'Production Technology I' }
];

const testMatch = (groupCode, groupName) => {
  const alias = (groupCode || groupName || '').toUpperCase();
  const cleanAlias = alias.replace(/[^A-Z0-9]/g, '');
  console.log(`\nTesting: groupCode="${groupCode}", groupName="${groupName}" -> cleanAlias="${cleanAlias}"`);
  
  if (!cleanAlias) {
    console.log("Empty clean alias, maps nothing.");
    return;
  }
  
  courses.forEach(c => {
    const codeUpper = c.code.toUpperCase();
    const cleanCodeUpper = codeUpper.replace(/[^A-Z0-9]/g, '');
    const isMatch = codeUpper.includes(alias) || cleanCodeUpper.includes(cleanAlias);
    if (isMatch) console.log(`  [MATCH] ${c.code}`);
  });
}

testMatch('MEC-3', 'Mechanical Engineering Yr3'); // MEC-3
testMatch(undefined, 'Mechanical Engineering Yr3'); // No group code
testMatch(undefined, 'Mechanical Engineering'); // No year
