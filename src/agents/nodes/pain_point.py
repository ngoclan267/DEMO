"""Pain Point Agent: gom cac phan hoi tuong tu thanh mot nhom van de (PRD 14).

Moi nhom (topic_label) duoc gan tieu de tieng Viet cu the (vd "Loi dang nhap /
xac thuc") thay vi hien thi thang ma noi bo (dang_nhap) hay nhan chung chung
"dich_vu" khong ro nghia; dong thoi dinh kem noi dung That cua vai phan hoi
tieu cuc lien quan (sample_posts) de nguoi dung/doanh nghiep bam vao xem ngay
khach hang dang phan nan cu the ve dieu gi, thay vi chi thay so luong."""
from collections import defaultdict

from src.agents.state import AgentState
from src.models.schemas import PainPoint, Severity, VerificationStatus

TOPIC_LABEL_TITLES = {
    "dang_nhap": "Lỗi đăng nhập / xác thực",
    "giao_dich": "Lỗi giao dịch / chuyển tiền",
    "bao_mat": "Bảo mật / khoá tài khoản",
    "nhan_vien": "Thái độ / chất lượng phục vụ của nhân viên",
    "dich_vu": "Chất lượng dịch vụ nói chung",
    "ung_dung": "Lỗi ứng dụng / hiệu năng",
    "chinh_sach": "Chính sách / biểu phí",
}

MAX_SAMPLE_POSTS = 20


def pain_point_node(state: AgentState) -> dict:
    content_by_post_id = {post.id: post.content for post in state.get("clean_posts", [])}

    groups: dict[str, list] = defaultdict(list)
    for pred in state.get("negative_predictions", []):
        groups[pred.topic_label].append(pred)

    pain_points = []
    for label, preds in groups.items():
        avg_severity = sum(p.severity_score for p in preds) / len(preds)
        avg_conf = sum(p.confidence_score for p in preds) / len(preds)
        label_title = TOPIC_LABEL_TITLES.get(label, label)

        ordered_preds = sorted(preds, key=lambda p: p.severity_score, reverse=True)
        sample_posts = []
        for p in ordered_preds:
            content = content_by_post_id.get(p.post_id)
            if content and content not in sample_posts:
                sample_posts.append(content)
            if len(sample_posts) >= MAX_SAMPLE_POSTS:
                break

        pain_points.append(
            PainPoint(
                topic_id=state["topic_id"],
                title=label_title,
                topic_label=label,
                description=f'{len(preds)} phản hồi tiêu cực liên quan đến "{label_title.lower()}".',
                post_count=len(preds),
                trend="up" if len(preds) > 5 else "flat",
                severity=Severity.HIGH if avg_severity > 0.7 else Severity.MEDIUM,
                verification_status=VerificationStatus.NEEDS_REVIEW,
                confidence_score=round(avg_conf, 2),
                sample_posts=sample_posts,
            )
        )
    return {"pain_points": pain_points}
