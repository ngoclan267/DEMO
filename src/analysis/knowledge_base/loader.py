import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent

# Trần số tài liệu topic-scoped lấy từ DB mỗi lần — kho crawl được (official_documents) có thể phình
# to theo thời gian, khác kho tĩnh vài file .md; giới hạn ở bước LOAD (mới nhất trước), rồi
# select_relevant_docs bên dưới lọc tiếp xuống số ít thực sự liên quan trước khi đưa vào prompt.
DEFAULT_TOPIC_DOCS_LOAD_LIMIT = 200
DEFAULT_RELEVANT_DOCS_LIMIT = 15
_MIN_TOKEN_LENGTH = 3

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass
class KnowledgeDoc:
    """Một tài liệu tham chiếu (quy định NHNN, thông báo chính thức ngân hàng...)."""

    id: str
    title: str
    url: str
    effective_date: str
    content: str


def _parse_doc(path: Path) -> KnowledgeDoc:
    raw = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        raise ValueError(f"Knowledge base doc thiếu frontmatter '---': {path}")

    frontmatter, content = match.groups()
    meta: dict[str, str] = {}
    for line in frontmatter.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()

    return KnowledgeDoc(
        id=meta["id"],
        title=meta["title"],
        url=meta["url"],
        effective_date=meta["effective_date"],
        content=content.strip(),
    )


def load_knowledge_base() -> list[KnowledgeDoc]:
    """Load toàn bộ tài liệu tham chiếu trong src/analysis/knowledge_base/*.md.

    Kho nhỏ (vài tài liệu), nên không cần vector DB — Verification Agent đưa thẳng toàn bộ nội
    dung này vào prompt LLM thay vì làm một bước retrieval riêng.

    QUAN TRỌNG — kho này KHÔNG được lọc theo topic, nên nội dung ở đây được đưa vào prompt xác minh
    của MỌI ngân hàng cùng lúc. Chỉ đặt ở đây văn bản thực sự áp dụng cho mọi ngân hàng (quy định/
    thông tư/quyết định của NHNN). TUYỆT ĐỐI không thêm thông báo/chính sách riêng của 1 ngân hàng cụ
    thể vào đây — từng có sự cố thật: thông báo riêng của SHB bị đặt nhầm vào kho toàn cục này khiến
    review của khách hàng TPBank bị đối chiếu (và match) với thông báo của SHB. Tài liệu riêng của 1
    ngân hàng phải vào bảng `official_documents` gắn đúng `topic_id` (qua BankWebsiteCollector khi
    có thể, hoặc seed thủ công — xem scripts/seed_data.py) để load_topic_documents() bên dưới tự lọc
    đúng phạm vi.
    """
    return [_parse_doc(path) for path in sorted(KNOWLEDGE_BASE_DIR.glob("*.md"))]


def format_knowledge_base_for_prompt(docs: list[KnowledgeDoc] | None = None) -> str:
    """Định dạng knowledge base thành văn bản để đưa vào prompt LLM."""
    docs = docs if docs is not None else load_knowledge_base()
    parts = [
        f"[{doc.id}] {doc.title}\nNguồn: {doc.url} (hiệu lực từ {doc.effective_date})\n{doc.content}" for doc in docs
    ]
    return "\n\n---\n\n".join(parts)


def load_topic_documents(
    session: Session, topic_id: UUID, limit: int = DEFAULT_TOPIC_DOCS_LOAD_LIMIT
) -> list[KnowledgeDoc]:
    """Tài liệu tham chiếu crawl được từ website ngân hàng (bảng official_documents), scope theo
    từng topic — bổ sung cho kho tĩnh toàn cục ở load_knowledge_base() (thông tư NHNN, áp dụng mọi
    ngân hàng). Import Post/OfficialDocument ở TRONG hàm để tránh vòng import
    (src.db.models không cần biết gì về analysis).

    Loại trừ category="news" — bài báo là tin BÊN THỨ BA (xem NewsApifyCollector), không phải văn
    bản CHÍNH THỨC của ngân hàng. Trộn vào đây sẽ làm sai lệch ý nghĩa reference_status ("matched"
    hiện có nghĩa "ngân hàng đã xác nhận chính thức", không phải "báo chí cũng đưa tin")."""
    from src.db.models import OfficialDocument

    rows = (
        session.query(OfficialDocument)
        .filter(OfficialDocument.topic_id == topic_id, OfficialDocument.category != "news")
        .order_by(OfficialDocument.published_at.desc().nullslast(), OfficialDocument.last_seen_at.desc())
        .limit(limit)
        .all()
    )
    return [
        KnowledgeDoc(
            id=str(doc.id),
            title=doc.title,
            url=doc.url,
            effective_date=str(doc.published_at or doc.last_seen_at or ""),
            content=doc.content or "",
        )
        for doc in rows
    ]


def _significant_tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"\w+", text, re.UNICODE) if len(token) >= _MIN_TOKEN_LENGTH}


def select_relevant_docs(
    post_content: str, docs: list[KnowledgeDoc], limit: int = DEFAULT_RELEVANT_DOCS_LIMIT
) -> list[KnowledgeDoc]:
    """Xếp hạng đơn giản theo số từ khoá (token) trùng giữa nội dung post và title+content tài
    liệu — đủ để chặn việc nhồi TOÀN BỘ kho (có thể lên tới hàng trăm tài liệu crawl được) vào
    prompt LLM. Không cần embedding/vector DB ở giai đoạn này vì kho còn nhỏ; nếu kho phình to hơn
    nữa, đây là chỗ nâng cấp lên retrieval bằng vector store (chroma_persist_dir đã có sẵn trong
    config nhưng chưa dùng)."""
    if len(docs) <= limit:
        return docs

    post_tokens = _significant_tokens(post_content)
    if not post_tokens:
        return docs[:limit]

    scored = [(len(post_tokens & _significant_tokens(f"{doc.title} {doc.content}")), doc) for doc in docs]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [doc for score, doc in scored[:limit] if score > 0] or docs[:limit]
