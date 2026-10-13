"""신고 테이블 (기획서 7.3 reports, 안전 묶음 PR 1)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("reporter_id", sa.BigInteger(), nullable=False),
        sa.Column("target_user_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("detail", sa.String(500), server_default="", nullable=False),
        sa.Column("status", sa.String(10), server_default="OPEN", nullable=False),
        sa.Column("resolution", sa.String(10), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reports"),
        sa.ForeignKeyConstraint(
            ["reporter_id"], ["users.id"], name="fk_reports_reporter_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["users.id"], name="fk_reports_target_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["items.id"], name="fk_reports_item_id_items"
        ),
        # 같은 글에서 같은 대상을 다시 신고하지 못한다
        sa.UniqueConstraint(
            "reporter_id",
            "target_user_id",
            "item_id",
            name="uq_reports_reporter_id_target_user_id_item_id",
        ),
        sa.CheckConstraint(
            "reason IN ('INAPPROPRIATE', 'FRAUD', 'THREAT', 'OTHER')",
            name=op.f("ck_reports_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'RESOLVED')", name=op.f("ck_reports_status")
        ),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN ('DISMISSED', 'SUSPENDED')",
            name=op.f("ck_reports_resolution"),
        ),
        # 자기 자신을 신고하지 못한다
        sa.CheckConstraint(
            "reporter_id <> target_user_id", name=op.f("ck_reports_self_report")
        ),
        # 사유가 '기타'이면 설명이 비어 있으면 안 된다
        sa.CheckConstraint(
            "reason <> 'OTHER' OR length(btrim(detail)) > 0",
            name=op.f("ck_reports_other_needs_detail"),
        ),
        # OPEN이면 처리 결과·시각이 없고, RESOLVED이면 둘 다 있다
        sa.CheckConstraint(
            "(status = 'OPEN' AND resolution IS NULL AND resolved_at IS NULL) OR "
            "(status = 'RESOLVED' AND resolution IS NOT NULL AND resolved_at IS NOT NULL)",
            name=op.f("ck_reports_resolved_consistency"),
        ),
    )
    op.create_index("ix_reports_status_created_at", "reports", ["status", "created_at"])
    # Supabase는 public 스키마를 REST로 자동 공개한다. 0001과 같이 RLS를 켜고 정책을 두지 않는다.
    op.execute("ALTER TABLE reports ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("reports")
