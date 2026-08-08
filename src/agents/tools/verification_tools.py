"""
Tools ho tro Verification Agent doi chieu voi nguon chinh thuc:
thong bao doanh nghiep, van ban phap ly, thong cao bao chi, bao chi uy tin (PRD 14).
"""
from langchain_core.tools import tool


@tool
def search_official_announcements(query: str) -> list[str]:
    """Tim kiem thong bao chinh thuc / van ban phap ly lien quan den truy van."""
    # Placeholder: trong production goi web-search / RAG tren kho van ban phap ly.
    return [f"Khong tim thay thong bao chinh thuc khop voi: {query}"]


@tool
def search_press_coverage(query: str) -> list[str]:
    """Tim kiem bai bao / thong cao bao chi lien quan den truy van."""
    return [f"Khong tim thay bai bao lien quan den: {query}"]
