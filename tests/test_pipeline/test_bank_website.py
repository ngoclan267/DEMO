from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from src.pipeline.collectors.bank_website import BankWebsiteCollector, _extract_main_text


def _fake_response(text: str, url: str = "https://tpbank.com.vn/tin-tuc") -> MagicMock:
    response = MagicMock()
    response.text = text
    # response.url dùng làm gốc resolve link tương đối (xem _discover_article_links) — phải là
    # string thật, không phải MagicMock mặc định, nếu không urljoin() sẽ ra kết quả vô nghĩa.
    response.url = url
    response.raise_for_status.return_value = None
    return response


LISTING_HTML = """
<html><body>
<a href="/tin-tuc/thong-bao-bao-tri-he-thong">Bảo trì hệ thống</a>
<a href="/tin-tuc/bieu-phi-moi">Biểu phí mới</a>
<a href="https://other-domain.com/x">Link ngoài</a>
<a href="/tin-tuc/thong-bao-bao-tri-he-thong#section">Link lặp (khác fragment)</a>
</body></html>
"""

ARTICLE_HTML = """
<html><head><title>Trang chủ</title>
<meta property="article:published_time" content="2026-08-01T10:00:00+07:00">
</head>
<body>
<nav>menu không liên quan</nav>
<article>
<h1>Thông báo bảo trì hệ thống</h1>
<p>Ngân hàng sẽ bảo trì hệ thống Internet Banking từ 23h00 đến 02h00 ngày 15/08/2026.</p>
<p>Trong thời gian này, một số dịch vụ có thể bị gián đoạn.</p>
</article>
<footer>footer không liên quan</footer>
</body></html>
"""


def test_bank_website_collector_discovers_and_fetches_new_articles():
    listing_response = _fake_response(LISTING_HTML)
    article_response = _fake_response(ARTICLE_HTML)

    with (
        patch("httpx.Client.get", side_effect=[listing_response, article_response, article_response]),
        patch("src.pipeline.collectors.bank_website.time.sleep"),
    ):
        collector = BankWebsiteCollector({"seed_urls": ["https://tpbank.com.vn/tin-tuc"]})
        result = collector.collect(limit=10)

    # 2 link nội bộ khác nhau (bảo trì + biểu phí) — link ngoài domain và link trùng (chỉ khác
    # fragment) bị loại.
    assert len(result) == 2
    urls = {doc.external_id for doc in result}
    assert "https://tpbank.com.vn/tin-tuc/thong-bao-bao-tri-he-thong" in urls
    assert "https://tpbank.com.vn/tin-tuc/bieu-phi-moi" in urls

    doc = next(d for d in result if "bao-tri" in d.external_id)
    assert "bảo trì hệ thống Internet Banking" in doc.content
    assert doc.raw["category"] == "maintenance"
    assert doc.raw["title"] == "Thông báo bảo trì hệ thống"
    assert doc.posted_at is not None


def test_bank_website_collector_skips_known_urls():
    listing_response = _fake_response(LISTING_HTML)

    known = {
        "https://tpbank.com.vn/tin-tuc/thong-bao-bao-tri-he-thong",
        "https://tpbank.com.vn/tin-tuc/bieu-phi-moi",
    }

    with patch("httpx.Client.get", return_value=listing_response) as mock_get:
        collector = BankWebsiteCollector({"seed_urls": ["https://tpbank.com.vn/tin-tuc"]})
        result = collector.collect(limit=10, known_ids=known)

    assert result == []
    # Chỉ gọi 1 lần để tải trang mục lục — không tải chi tiết bài viết nào vì cả 2 URL đều đã biết.
    mock_get.assert_called_once()


def test_bank_website_collector_one_article_failure_does_not_break_batch():
    listing_response = _fake_response(LISTING_HTML)
    article_response = _fake_response(ARTICLE_HTML)

    with (
        patch("httpx.Client.get", side_effect=[listing_response, Exception("network error"), article_response]),
        patch("src.pipeline.collectors.bank_website.time.sleep"),
    ):
        collector = BankWebsiteCollector({"seed_urls": ["https://tpbank.com.vn/tin-tuc"]})
        result = collector.collect(limit=10)

    assert len(result) == 1


def test_bank_website_collector_requires_seed_urls():
    collector = BankWebsiteCollector({})
    try:
        collector.collect()
        raise AssertionError("Phải raise ValueError khi thiếu seed_urls")
    except ValueError:
        pass


def test_extract_main_text_prefers_h1_ancestor_over_larger_sitewide_banner():
    """Hồi quy: kiểm chứng thực tế trên trang ngân hàng thật (tpb.vn) cho thấy heuristic cũ (chọn
    khối có tổng độ dài <p> lớn nhất TOÀN TRANG) chọn nhầm 1 banner/CTA lặp lại ở nhiều trang thay
    vì nội dung bài viết thật, vì banner đó có tổng text dài hơn. Bám theo tổ tiên gần nhất của
    <h1> phải tránh được lỗi này."""
    html = """
    <html><body>
    <div class="sitewide-banner">
    <p>Đăng ký ngay hôm nay để nhận ưu đãi khủng dành cho khách hàng mới của ngân hàng chúng tôi</p>
    <p>Tải ứng dụng ngay trên App Store và Google Play để trải nghiệm dịch vụ ngân hàng số hiện đại</p>
    <p>Liên hệ tổng đài chăm sóc khách hàng 24/7 nếu bạn cần hỗ trợ thêm về sản phẩm dịch vụ</p>
    </div>
    <div class="news-detail">
    <h1>Thông báo bảo trì hệ thống</h1>
    <p>Ngân hàng sẽ bảo trì hệ thống Internet Banking từ 23h00 đến 02h00 ngày 15/08/2026.</p>
    </div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")

    result = _extract_main_text(soup)

    assert "bảo trì hệ thống Internet Banking" in result
    assert "Đăng ký ngay hôm nay" not in result


def test_get_collector_dispatches_bank_website():
    from src.pipeline.collectors import get_collector

    collector = get_collector("bank_website", {"seed_urls": ["https://x.com"]})
    assert isinstance(collector, BankWebsiteCollector)
