"""official_documents: thêm sentiment/sentiment_classified_at cho tin bên thứ ba (category="news")

News Sentiment Agent (xem src/analysis/news_classification.py) đánh giá sắc thái đưa tin (tích cực/
trung lập/tiêu cực) cho bài báo thu thập qua NewsApifyCollector — nhẹ hơn nhiều so với
Classification/Verification/Consensus đầy đủ dùng cho phản hồi khách hàng (chỉ cần 1 field
sentiment, không cần topic_label/severity/đối chiếu chính sách). Dùng chung enum "sentiment_type"
đã có sẵn từ migration 0001 (predictions.sentiment) — cùng ý nghĩa positive/neutral/negative.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    # create_type=False: "sentiment_type" đã tồn tại từ migration 0001 (cột predictions.sentiment) —
    # không được để Alembic tự CREATE TYPE lại, sẽ lỗi "type already exists".
    sentiment_type = sa.Enum("positive", "neutral", "negative", name="sentiment_type", create_type=False)
    op.add_column("official_documents", sa.Column("sentiment", sentiment_type, nullable=True))
    op.add_column("official_documents", sa.Column("sentiment_classified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("official_documents", "sentiment_classified_at")
    op.drop_column("official_documents", "sentiment")
