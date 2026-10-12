"""기획서 7장 초기 스키마: users, items, reservations

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("nickname", sa.String(20), nullable=False),
        sa.Column("lat", sa.Numeric(4, 2), nullable=False),
        sa.Column("lng", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("category", sa.String(10), server_default="ETC", nullable=False),
        sa.Column("title", sa.String(50), nullable=False),
        sa.Column("total_slots", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Integer(), nullable=False),
        sa.Column("price_per_slot", sa.Integer(), nullable=False),
        sa.Column("filled_slots", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lat", sa.Numeric(4, 2), nullable=False),
        sa.Column("lng", sa.Numeric(5, 2), nullable=False),
        sa.Column("pickup_note", sa.String(200), nullable=False),
        sa.Column("product_url", sa.String(500), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("status", sa.String(10), server_default="OPEN", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_items"),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name="fk_items_owner_id_users"
        ),
        sa.CheckConstraint(
            "type IN ('GROUP_BUY', 'SHARE')", name=op.f("ck_items_type")
        ),
        sa.CheckConstraint(
            "category IN ('FRUIT_VEG', 'FOOD', 'HOUSEHOLD', 'ETC')",
            name=op.f("ck_items_category"),
        ),
        sa.CheckConstraint(
            "total_slots BETWEEN 1 AND 20", name=op.f("ck_items_total_slots")
        ),
        sa.CheckConstraint("total_price >= 0", name=op.f("ck_items_total_price")),
        sa.CheckConstraint(
            "filled_slots >= 0 AND filled_slots <= total_slots",
            name=op.f("ck_items_filled_slots"),
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CONFIRMED', 'FAILED', 'CANCELED')",
            name=op.f("ck_items_status"),
        ),
        sa.CheckConstraint(
            "type <> 'SHARE' OR (total_slots = 1 AND total_price = 0 AND image_url IS NOT NULL)",
            name=op.f("ck_items_share_rule"),
        ),
    )
    op.create_index("ix_items_status_deadline", "items", ["status", "deadline"])
    op.create_index("ix_items_owner_id", "items", ["owner_id"])

    op.create_table(
        "reservations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reservations"),
        sa.ForeignKeyConstraint(
            ["item_id"], ["items.id"], name="fk_reservations_item_id_items"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_reservations_user_id_users"
        ),
        sa.UniqueConstraint(
            "item_id", "user_id", name="uq_reservations_item_id_user_id"
        ),
    )
    op.create_index("ix_reservations_user_id", "reservations", ["user_id"])

    # Supabase는 public 스키마를 REST(Data API)로 자동 공개한다.
    # RLS를 켜고 정책을 두지 않아 그 경로를 전부 막는다. 테이블 소유자인 백엔드는 영향받지 않는다.
    for table in ("users", "items", "reservations"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("reservations")
    op.drop_table("items")
    op.drop_table("users")
