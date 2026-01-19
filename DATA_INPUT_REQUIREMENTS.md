# DATA INPUT REQUIREMENTS FOR SYSTEMATIC TIMETABLE GENERATION

## Based on Manual Timetable Format Analysis

---

## 1. **COURSES** - What to Capture

### Current Fields: ✅
- `code` (e.g., CEE 3111)
- `name`
- `department_id`
- `level` (2, 3, 4, 5)
- `credits`
- `lecture_hours`
- `tutorial_hours`
- `practical_hours`

### **REQUIRED ADDITIONS:**

#### A. **Room Type Preferences** (New Field)
```
preferred_room_type: string (enum)
Options:
- "lecture_hall"      → MLT, LT, ENLT1, ENLT2, NLR1, NLR2, OM1, OM2, PLT1, PLT2, LT2
- "drawing_room"      → D1, D2, D3, D4
- "seminar_room"      → S3, S4, S5, CONF
- "lab"               → MLAB, COMP, SPL, MPR, BLT
- "surveying_room"    → G01, G02, G03, G04, G05
- "any"               → No specific requirement
```

#### B. **Course Type** (New Field)
```
course_type: string (enum)
Options:
- "department_specific"  → Only for students in that department
- "general"              → Shared across multiple departments (e.g., MAT 2110, MAT 3110, ENG 2139)
- "multi_department"     → Taken by multiple specific departments
```

#### C. **Session Split Logic** (New Field)
```
session_configuration: JSON
{
  "lecture_sessions": 2,      // How many 2-hour lecture blocks
  "tutorial_sessions": 1,     // How many 2-hour tutorial blocks
  "practical_sessions": 2,    // How many 2-hour practical blocks
  "requires_consecutive": false  // Must sessions be back-to-back?
}
```

#### D. **Group Division Requirements** (New Field)
```
group_division_type: string (enum)
Options:
- "full_group"        → All students together (e.g., MAT 3110)
- "lab_groups"        → Divided into A, B, C, D groups (alternating)
- "drawing_groups"    → Divided into D1, D2, D3, D4 groups
- "tutorial_groups"   → Divided for tutorials
```

### **Upload Page Should Capture:**
```
Course Code: CEE 3111
Course Name: Fluid Mechanics
Department: CEE
Level: 3
Credits: 3

Contact Hours:
├─ Lectures: 4 hours → Auto-convert to 2 sessions (2 hours each)
├─ Tutorials: 2 hours → Auto-convert to 1 session (2 hours)
└─ Practicals: 2 hours → Auto-convert to 1 session (2 hours)

Room Requirements:
├─ Lecture Room Type: lecture_hall
├─ Tutorial Room Type: any
└─ Practical Room Type: lab

Course Type: department_specific
Group Division:
├─ Lectures: full_group
├─ Tutorials: tutorial_groups (divide class)
└─ Practicals: lab_groups (divide into A, B, C, D)
```

---

## 2. **STUDENT GROUPS** - What to Capture

### Current Fields: ✅
- `name`
- `level`
- `department_id`
- `size`

### **REQUIRED ADDITIONS:**

#### A. **Group Type Classification** (New Field)
```
group_type: string (enum)
Options:
- "general"          → GEN1, GEN2 (2nd year only)
- "department"       → AEN, CEE, EEE, GEE, MEC (3rd-5th year)
- "lab_group"        → A, B, C, D (subdivisions for labs)
- "drawing_group"    → D1, D2, D3, D4 (for drawing courses)
- "tutorial_group"   → Custom tutorial subdivisions
```

#### B. **Parent Group Reference** (New Field)
```
parent_group_id: int (nullable)
Example:
- GEN1 (parent_group_id: null)
  ├─ GEN1-A (parent_group_id: GEN1.id)
  ├─ GEN1-B (parent_group_id: GEN1.id)
  ├─ GEN1-C (parent_group_id: GEN1.id)
  └─ GEN1-D (parent_group_id: GEN1.id)
```

#### C. **Display Code** (New Field)
```
display_code: string
Examples:
- "GEN1" for General Group 1
- "AEN" for Agricultural Engineering
- "D3" for Drawing Group 3
- "A" for Lab Group A
```

### **System Auto-Generation Logic:**
```
When creating groups:
1. Level 2 → Create GEN1, GEN2 automatically
   └─ Option to subdivide into A, B, C, D if needed

2. Levels 3-5 → Create department groups automatically
   - AEN (Agricultural Engineering)
   - CEE (Civil & Environmental Engineering)
   - EEE (Electrical & Electronics Engineering)
   - GEE (Geomatics Engineering)
   - MEC (Mechanical Engineering)
   
3. For each department group → Option to create subgroups
   ├─ Lab groups: A, B, C, D
   ├─ Drawing groups: D1, D2, D3, D4
   └─ Tutorial groups: As needed
```

---

## 3. **ROOMS** - What to Capture

### Current Fields: ✅
- `name` (e.g., MLT, ENLT1)
- `building`
- `capacity`
- `room_type`
- `has_projector`
- `has_computers`

### **REQUIRED ADDITIONS:**

#### A. **Standard Room Codes** (Enforce)
```
Use exact codes from manual timetable:

Lecture Halls:
- MLT (School of Mines Lecture Theatre)
- LT (Lecture Theatre, School of Engineering)
- ENLT1, ENLT2 (Engineering New Lecture Theatre 1, 2)
- NLR1, NLR2 (New Lecture Rooms)
- OM1, OM2 (Omnia Lecture Theatre)
- PLT1, PLT2 (Population Lecture Theatre)
- LT2 (Lecture Theatre, School of Natural Sciences)

Labs:
- MLAB (Lab Room, Agric. Engineering)
- COMP (Computer Room, Agric. Engineering)
- SPL (Soil Physics Lab)
- MPR (Microprocessor room)
- BLT (Botany Lab)

Seminar/Tutorial Rooms:
- S3, S4, S5 (Seminar Rooms)
- TRA, TRB (Tutorial Rooms A & B)
- CONF (Conference Room)

Drawing Rooms:
- D1, D2, D3, D4 (Drawing Rooms)

Surveying Building:
- G01, G02, G03, G04, G05 (Ground Floor Rooms)
```

#### B. **Room Category** (Refined Field)
```
room_category: string (enum)
Options:
- "lecture_hall_large"   → 100+ capacity
- "lecture_hall_medium"  → 50-100 capacity
- "lecture_hall_small"   → 30-50 capacity
- "drawing_room"         → For engineering drawing
- "computer_lab"         → Has computers
- "mechanical_lab"       → For mechanical practicals
- "electrical_lab"       → For electrical practicals
- "surveying_room"       → For geomatics
- "seminar_room"         → Small group discussions
- "conference_room"      → For meetings/tutorials
```

#### C. **Department Affinity** (New Field)
```
department_affinity: string (nullable)
Examples:
- G01-G05 → "GEE" (Surveying Building for Geomatics)
- MLAB, COMP, CONF → "AEN" (Agricultural Engineering)
- D1-D4 → "general" (All engineering departments)
```

### **Upload Page Should Have:**
```
Room Code: ENLT1 (auto-suggest from standard codes)
Full Name: Engineering New Lecture Theatre 1
Building: School of Engineering - New Building
Capacity: 120
Category: lecture_hall_medium
Department Affinity: general (or specific department)
Facilities:
├─ Projector: Yes
├─ Computers: No
├─ Air Conditioning: Yes
└─ Whiteboard: Yes
```

---

## 4. **LECTURERS** - What to Capture

### Current Fields: ✅
- `staff_number`
- `full_name`
- `email`
- `department_id`
- `max_hours_per_week`

### **REQUIRED ADDITIONS:**

#### A. **Teaching Preferences** (New Field)
```
teaching_preferences: JSON
{
  "preferred_days": ["Monday", "Tuesday", "Wednesday"],
  "avoid_early_morning": false,    // Before 8:00
  "avoid_late_evening": true,      // After 17:00
  "preferred_time_blocks": ["08:00-12:00", "14:00-16:00"],
  "max_consecutive_hours": 4
}
```

#### B. **Expertise Level** (New Field)
```
For each course assignment, add:
- "primary" → Main lecturer
- "assistant" → Co-lecturer/backup
```

### **Upload Remains Simple:**
```
Staff Number: ABC123
Full Name: Dr. John Banda
Email: john.banda@unza.zm
Department: CEE
Max Teaching Hours/Week: 20

Unavailability (optional):
└─ Thursday 14:00-17:00 (faculty meetings)
```

---

## 5. **COURSE-GROUP-LECTURER ASSIGNMENTS**

### **NEW UNIFIED ASSIGNMENT TABLE NEEDED:**
```
course_session_assignments:
├─ course_id
├─ group_id (or multiple groups)
├─ lecturer_id
├─ session_type (lecture/tutorial/practical)
├─ room_preference
├─ group_division_required (boolean)
└─ notes
```

### **Example Assignment Entry:**
```
Course: CEE 3111
Session Type: Lecture
Groups: CEE-3rd (full group)
Lecturer: Dr. Mumba
Room Preference: lecture_hall
Division Required: No

Course: CEE 3111
Session Type: Practical
Groups: CEE-3rd-A, CEE-3rd-B, CEE-3rd-C
Lecturer: Mr. Phiri
Room Preference: lab
Division Required: Yes (alternating weeks)
```

---

## 6. **GENERATION ALGORITHM ADJUSTMENTS**

### **Key Changes Needed:**

1. **Room Assignment Logic:**
   ```
   - Match course room preference to available rooms
   - Consider department affinity
   - Check capacity against group size
   ```

2. **Group Handling:**
   ```
   - For "general" courses (MAT 3110):
     - Schedule same time for all departments at level
     - Use multiple rooms if needed
   
   - For "department_specific" courses:
     - Schedule only for that department's groups
   
   - For divided groups (A, B, C, D):
     - Schedule separate sessions
     - Can use same time slots (different rooms)
   ```

3. **2-Hour Block Enforcement:**
   ```
   - Each scheduled session = 2 consecutive hours
   - Display as continuous block in output
   ```

4. **Session Type Tracking:**
   ```
   - Maintain count of:
     - Lectures scheduled
     - Tutorials scheduled
     - Practicals scheduled
   - Until all required sessions are assigned
   ```

---

## 7. **OUTPUT FORMAT GENERATION**

### **Required Export Function:**
```python
def export_timetable_traditional_format(timetable_id):
    """
    Generate table matching manual format:
    - Rows: Hourly time slots (07:00-19:00)
    - Columns: 2nd Year (GEN1, GEN2) | 3rd-5th (AEN, CEE, EEE, GEE, MEC)
    - Cells: Course Code + Room Code
    - Merge cells for 2+ hour sessions
    """
    return excel_file, pdf_file
```

---

## **IMPLEMENTATION PRIORITY:**

### Phase 1: Database Schema Updates ⚡
- [ ] Add new fields to models
- [ ] Create migration scripts
- [ ] Update schemas.py

### Phase 2: Frontend Input Forms 📝
- [ ] Update course upload with new fields
- [ ] Add group auto-generation
- [ ] Add room standard codes dropdown
- [ ] Enhanced assignment interface

### Phase 3: Generation Algorithm 🧮
- [ ] Room matching logic
- [ ] Group division handling
- [ ] General course scheduling
- [ ] Session type tracking

### Phase 4: Export/Display 📊
- [ ] Traditional table format generator
- [ ] Excel export
- [ ] PDF generation
- [ ] Conflict report

---

## **NEXT STEPS:**

1. **Approve this data structure**
2. **Start with database model updates**
3. **Update frontend forms**
4. **Enhance generation algorithm**
5. **Create export functionality**

Would you like me to start implementing these changes?
