"""users: thêm trạng thái dùng thử/đã thanh toán + bảng payments cho tích hợp VNPay

Tài khoản do platform admin tạo (POST /topics/admin) giờ có 2 loại: "dùng thử" (has hạn N ngày,
hết hạn thì khoá đăng nhập, xem check 402 trong routes_auth.py::login) và "chính thức" (không giới
hạn). Nâng cấp từ dùng thử lên chính thức = thanh toán qua VNPay (xem src/billing/). is_paid mặc
định true để mọi user hiện có (tự đăng ký qua /register, tài khoản demo) không bị ảnh hưởng —
chỉ tài khoản admin tạo ở chế độ "dùng thử" mới có false + trial_ends_at.

checkout_token/checkout_token_expires_at: token ngắn hạn cấp lúc login bị chặn vì hết hạn dùng
thử, dùng gọi API thanh toán mà KHÔNG cần JWT (tài khoản chưa/không có session lúc này) — cùng
pattern với reset_token đã có.

payments: đối soát giao dịch VNPay, chống xử lý trùng IPN (unique txn_ref).

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_paid", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("users", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("checkout_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("checkout_token_expires_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("txn_ref", sa.String(64), nullable=False, unique=True),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("payments")
    op.drop_column("users", "checkout_token_expires_at")
    op.drop_column("users", "checkout_token")
    op.drop_column("users", "trial_ends_at")
    op.drop_column("users", "is_paid")
