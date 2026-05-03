import re

path = "/home/on3/DENNIS/TABLESYS/backend/app/services/timetable_generator.py"
with open(path, "r") as f:
    text = f.read()

# Fix 1: The Indentation Scope bug.
# We need to indent everything from "group_size_map" down to the end of the `session` block.
# Actually, the block starting from `# Build a group-size map` up to `# --- Phase 3:`
# Let's find `# Build a group-size map for capacity filtering`.
lines = text.split("\n")

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if "# Build a group-size map for capacity filtering" in line:
        start_idx = i
    if "            # --- Phase 3:" in line and start_idx != -1:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    print(f"Indenting lines {start_idx} to {end_idx - 1}...")
    for i in range(start_idx, end_idx):
        if lines[i].strip() != "":
            # Indent by 4 spaces
            lines[i] = "    " + lines[i]

# Fix 2: C1 Legacy Table Usage
# Find C1 section
for i, line in enumerate(lines):
    if "# C1. Each Session must be assigned exactly once per Group" in line:
        c1_start = i
        break

c1_end = -1
for i in range(c1_start, len(lines)):
    if "# C2. Room Capacity / Overlap" in line or "for day_idx in range" in line:
        c1_end = i
        break

c1_replacement = """        # C1. Each Session must be assigned exactly once per Group
        for course in courses:
            assigned_groups = []
            cgl_links = self.db.query(CourseGroupLink).filter(CourseGroupLink.course_id == course.id, CourseGroupLink.session_type == 'lecture').all()
            if cgl_links:
                assigned_groups = list(set([l.shared_batch_id if l.is_shared else l.group_id for l in cgl_links]))
            else:
                ga = self.db.query(GroupAssignment).filter(GroupAssignment.course_id == course.id).all()
                assigned_groups = [g.group_id for g in ga]
                
            for main_group_id in assigned_groups:
                for session in course_sessions[course.id]:
                    session_vars = []
                    for k, var in vars_store.items():
                        if k[0] == course.id and k[1] == main_group_id and k[2] == session['s_id']:
                            session_vars.append(var)
                    
                    if session_vars:
                        model.Add(sum(session_vars) == 1)
"""
# Replace lines[c1_start:c1_end] with c1_replacement
new_lines = lines[:c1_start] + c1_replacement.split("\n")[:-1] + lines[c1_end:]
lines = new_lines

# Fix 3: start_hour hardcode
for i, line in enumerate(lines):
    if "start_hour = 7 + start_t" in line:
        lines[i] = line.replace("7 + start_t", "self.start_hour + start_t")


# Fix 4: NameError Duration in Section 4.3 Objective
for i, line in enumerate(lines):
    if "start_t + duration > 10:" in line and "if prefs.get" in line:
        # insert duration defined before
        lines[i] = "                    duration = course_sessions[course_id][s_id]['duration']\n" + lines[i]

# Fix 5: Unique Groups fragilty & C6 duplication & extend() RAM bloat
# We will completely rewrite C5 and sliding window, keeping them outside the day_idx loops.
c4_start = -1
c6_end = -1
for i, line in enumerate(lines):
    if "# --- C5. Daily Load Balancer (Neural Smoothing) ---" in line:
        c4_start = i
    if "# 4. Soft Constraints & Objectives" in line:
        c6_end = i
        break

if c4_start != -1 and c6_end != -1:
    c5_replacement = """            # Ensure students don't have "Marathon Days" (> 8 hours)
            unique_groups_all = list(set([k[1] for k in vars_store.keys()]))
            for group_id in unique_groups_all:
                for day_idx_loop in range(len(self.days)):
                    daily_vars = []
                    for k, var in vars_store.items():
                        if k[3] == day_idx_loop and k[1] == group_id:
                            duration = course_sessions[k[0]][k[2]]['duration']
                            daily_vars.append(var * duration)
                    
                    if daily_vars:
                        # Hard Constraint: Max 8 hours per day
                        model.Add(sum(daily_vars) <= 8)
                        
            # --- C6. Break / Fatigue Constraints (Sliding Window) ---
            for group_id in unique_groups_all:
                for day_idx_loop in range(len(self.days)):
                    for window_start in range(12 - 5 + 1):
                        window_vars = []
                        for k, var in vars_store.items():
                            if k[1] == group_id and k[3] == day_idx_loop:
                                start_t = k[4]
                                duration = course_sessions[k[0]][k[2]]['duration']
                                end_t = start_t + duration
                                
                                overlap_start = max(start_t, window_start)
                                overlap_end = min(end_t, window_start + 5)
                                
                                if overlap_start < overlap_end:
                                    overlap_hours = overlap_end - overlap_start
                                    window_vars.append(var * overlap_hours)
                        
                        if window_vars:
                            model.Add(sum(window_vars) <= 4)
"""
    new_lines = lines[:c4_start] + c5_replacement.split("\n")[:-1] + lines[c6_end:]
    lines = new_lines

with open(path, "w") as f:
    f.write("\n".join(lines))
    
print("Refactor applied.")
