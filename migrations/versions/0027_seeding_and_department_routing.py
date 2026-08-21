"""3 tính năng mới: phát hiện seeding, phòng ban theo nhân viên, tự động phân việc theo phòng ban.

- predictions.is_seeding/seeding_reasoning: cờ + lý do phát hiện review/bình luận giả mạo (Seeding
  Agent, xem src/analysis/graph.py::detect_seeding_node). CHỈ cảnh báo, không tự loại khỏi pain
  point (khác is_spam/is_duplicate) — mặc định is_seeding=False, không đổi hành vi post đã có.
- topic_members.department: phòng ban của nhân viên trong TỪNG chủ đề (free text, không enum —
  cùng lý do department trên pain_points, cơ cấu phòng ban ngân hàng hay đổi).
- topics.auto_assign_enabled: bật/tắt tự động gán phòng ban cho pain point mới — mặc định TẮT
  (opt-in, khác notify_enabled mặc định bật).
- llm_call_type thêm "seeding_detection", "department_routing" — usage tracking cho 2 lượt gọi LLM
  mới (Seeding Agent, department routing khi auto_assign_enabled bật).
- notification_type thêm "department_assigned" — thông báo hệ thống tự gán phòng ban, gửi tới CẢ
  phòng ban (không phải 1 assigned_user_id cụ thể như "assigned").

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("predictions", sa.Column("is_seeding", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("predictions", sa.Column("seeding_reasoning", sa.Text(), nullable=True))

    op.add_column("topic_members", sa.Column("department", sa.String(length=100), nullable=True))

    op.add_column("topics", sa.Column("auto_assign_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))

    # ALTER TYPE ... ADD VALUE chạy được trong transaction từ PG 12+ (dự án dùng PG 16/17) — xem
    # ghi chú tương tự ở 0024_cross_check.py.
    op.execute("ALTER TYPE llm_call_type ADD VALUE IF NOT EXISTS 'seeding_detection'")
    op.execute("ALTER TYPE llm_call_type ADD VALUE IF NOT EXISTS 'department_routing'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'department_assigned'")


def downgrade():
    # Không có cách xoá giá trị khỏi Postgres ENUM mà không rebuild lại cả type — chỉ hoàn tác cột,
    # giữ nguyên các giá trị enum đã thêm (vô hại nếu không dùng tới), đúng tiền lệ 0024.
    op.drop_column("topics", "auto_assign_enabled")
    op.drop_column("topic_members", "department")
    op.drop_column("predictions", "seeding_reasoning")
    op.drop_column("predictions", "is_seeding")
