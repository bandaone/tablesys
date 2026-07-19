"""Scope department uniqueness by university.

Revision ID: b12f6a4c9d10
Revises: da3592bf282d
Create Date: 2026-05-10 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b12f6a4c9d10"
down_revision: Union[str, None] = "da3592bf282d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("departments_name_key", "departments", type_="unique")
    op.drop_constraint("departments_code_key", "departments", type_="unique")
    op.create_unique_constraint("uq_dept_univ_name", "departments", ["university_id", "name"])
    op.create_unique_constraint("uq_dept_univ_code", "departments", ["university_id", "code"])


def downgrade() -> None:
    op.drop_constraint("uq_dept_univ_name", "departments", type_="unique")
    op.drop_constraint("uq_dept_univ_code", "departments", type_="unique")
    op.create_unique_constraint("departments_name_key", "departments", ["name"])
    op.create_unique_constraint("departments_code_key", "departments", ["code"])
