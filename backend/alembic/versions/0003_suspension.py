"""계정 정지와 관리 감사 기록 (기획서 7.3 users 컬럼, admin_actions, 안전 묶음 PR 2)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("status", sa.String(10), server_default="ACTIVE", nullable=False),
    )
    op.add_column("users", sa.Column("suspended_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("suspension_reason", sa.String(500)))
    op.create_check_constraint(
        op.f("ck_users_status"), "users", "status IN ('ACTIVE', 'SUSPENDED')"
    )
    # 정지 상태와 정지 시각은 항상 함께 있거나 함께 없다
    op.create_check_constraint(
        op.f("ck_users_suspended_consistency"),
        "users",
        "(status = 'SUSPENDED') = (suspended_at IS NOT NULL)",
    )

    op.create_table(
        "admin_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("target_user_id", sa.BigInteger(), nullable=False),
        sa.Column("report_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_os_user", sa.String(100), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admin_actions"),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["users.id"], name="fk_admin_actions_target_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["report_id"], ["reports.id"], name="fk_admin_actions_report_id_reports"
        ),
        sa.CheckConstraint(
            "action IN ('SUSPEND', 'UNSUSPEND', 'RESOLVE_REPORT', 'VERIFY_EMAIL')",
            name=op.f("ck_admin_actions_action"),
        ),
    )
    op.create_index("ix_admin_actions_target_user_id", "admin_actions", ["target_user_id"])
    op.execute("ALTER TABLE admin_actions ENABLE ROW LEVEL SECURITY")
    # 추가 전용: 이 표는 고치거나 지우지 않는다(기획서 5.9 보존). 앱이 쓰는 역할에서도 막는 것은 운영 전 과제.


def downgrade() -> None:
    op.drop_table("admin_actions")
    op.drop_constraint(op.f("ck_users_suspended_consistency"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_status"), "users", type_="check")
    op.drop_column("users", "suspension_reason")
    op.drop_column("users", "suspended_at")
    op.drop_column("users", "status")
