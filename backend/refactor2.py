import sys

path = "/home/on3/DENNIS/TABLESYS/backend/app/services/timetable_generator.py"
with open(path, "r") as f:
    text = f.read()

lines = text.split("\n")

# Find variables creation loop:
# "vars_store[key] = var" is around line 700.
# Let's insert a tracking structure a bit before this.
for i, line in enumerate(lines):
    if "vars_store: Dict[tuple, Any] = {}" in line:
        lines.insert(i+1, "        var_group_mapping = {}  # var_name -> list of group_ids")
        break

# Now down at variable creation:
for i, line in enumerate(lines):
    if "vars_store[key] = var" in line:
        # Before this line, possible_groups has `primary_group_id` which only maps 1 group.
        # But wait, where is `assigned_main_group_ids`? It's defined at the batch level!
        lines.insert(i+1, "                                    var_group_mapping[var_name] = assigned_main_group_ids if batch_is_shared and session_type == 'lecture' else [group_id]")
        break

# Now update C4 & C5 to use var_group_mapping
c4_start = -1
for i, line in enumerate(lines):
    if "unique_groups_all = list(set([k[1] for k in vars_store.keys()]))" in line:
        c4_start = i
        break

if c4_start != -1:
    lines[c4_start] = """            # Collect all groups actively represented in ANY variable
            unique_groups_all = set()
            for g_list in var_group_mapping.values():
                unique_groups_all.update(g_list)
"""

# Update filtering in C4
for i, line in enumerate(lines):
    if "if k[3] == day_idx_loop and k[1] == group_id:" in line:
        lines[i] = "                        if k[3] == day_idx_loop and group_id in var_group_mapping[var.Name()]:"

# Update filtering in C5/C6 Break constraints
for i, line in enumerate(lines):
    if "if k[1] == group_id and k[3] == day_idx_loop:" in line:
        lines[i] = "                            if group_id in var_group_mapping[var.Name()] and k[3] == day_idx_loop:"

with open(path, "w") as f:
    f.write("\n".join(lines))
    
print("Refactor 2 applied.")
