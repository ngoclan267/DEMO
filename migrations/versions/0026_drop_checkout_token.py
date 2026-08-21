"""users: gỡ checkout_token/checkout_token_expires_at — hết hạn dùng thử không còn khoá đăng nhập

Trước đây: hết hạn dùng thử (thời gian hoặc trần trọn đời) làm login() trả 402, cấp checkout_token
ngắn hạn để tự nâng cấp qua VNPay mà KHÔNG cần JWT (tài khoản chưa/không có session lúc đó — xem
POST /billing/checkout cũ). Giờ: hết hạn dùng thử KHÔNG khoá đăng nhập nữa (chỉ tạm dừng phân tích
+ hiện banner mời nâng cấp trong dashboard, xem UserResponse.trial_expired) — luôn CÓ session hợp
lệ để gọi thẳng POST /billing/checkout (đổi tên từ /billing/checkout-authenticated, dùng JWT bình
thường), checkout_token không còn nơi nào set/đọc.

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("users", "checkout_token_expires_at")
    op.drop_column("users", "checkout_token")


def downgrade():
    op.add_column("users", sa.Column("checkout_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("checkout_token_expires_at", sa.DateTime(timezone=True), nullable=True))
