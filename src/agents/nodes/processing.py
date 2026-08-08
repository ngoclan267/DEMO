"""Processing Agent: loai bo trung lap, lam sach van ban, loai bo spam (PRD 14).

Loai bo trung lap gom 2 lop: trong cung 1 batch crawl (seen set) VA voi du lieu
da luu tu cac chu ky truoc (filter_new_posts) - lop thu 2 dam bao cung 1 phan
hoi khong bi Classification/Pain Point dem lai nhieu lan khi crawler tra ve lai
review cu o chu ky sau (xem repository.add_pain_points cong don post_count)."""
from src.agents.state import AgentState
from src.db.repository import filter_new_posts


def processing_node(state: AgentState) -> dict:
    seen = set()
    clean = []
    for post in state.get("raw_posts", []):
        key = post.content.strip().lower()
        if key in seen or len(key) < 3:
            continue
        seen.add(key)
        post.content = " ".join(post.content.split())
        clean.append(post)
    return {"clean_posts": filter_new_posts(clean)}
