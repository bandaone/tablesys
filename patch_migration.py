with open("backend/alembic/versions/af108f22f33c_initial_baseline_schema.py", "r") as f:
    contents = f.read()

audit_table_code = """
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column('user_email', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('entity_name', sa.String(), nullable=True),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('timestamp', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
"""

if "create_table('audit_logs'" not in contents:
    parts = contents.split("    # ### end Alembic commands ###", 1)
    new_contents = parts[0] + audit_table_code + "    # ### end Alembic commands ###" + parts[1]
    with open("backend/alembic/versions/af108f22f33c_initial_baseline_schema.py", "w") as f:
        f.write(new_contents)
