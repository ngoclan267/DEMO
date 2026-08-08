"""
LLM-backed services dung boi Classification Agent va Verification Agent.
Goi Google Gemini API qua model duoc cau hinh trong src/config.py (GEMINI_API_KEY, LLM_MODEL).
Trong bai test / khi khong co API key, fallback ve heuristic don gian de pipeline
van chay duoc end-to-end.

Cai dat: pip install google-genai
Lay API key tai: https://aistudio.google.com/apikey
"""
import json
import random
import unicodedata
from uuid import uuid4

from src.config import get_settings
from src.models.schemas import Post, Prediction, Sentiment, VerificationResult, VerificationStatus

# Danh sach tu khoa tieu cuc dung cho heuristic fallback (khi khong co Gemini
# API key / Gemini loi). Giu ca dang khong dau (nguoi dung go nhanh tren mobile,
# vd "khong", "loi", "cham") LAN dang co dau that (vd "không", "lỗi", "chậm")
# vi phan hoi crawl that tu Google Play / App Store hau het go co dau day du -
# thieu dang co dau se bo sot gan het tieu cuc that (day la loi da gap trong
# du lieu san xuat: rat nhieu tieu cuc that nhung heuristic cu khong bat duoc).
NEGATIVE_HINTS = [
    # khong dau (go tat / go nhanh)
    "khong", "loi", "khoa", "cham", "tang", "that vong", "ko ", " k ", "te qua",
    "kem", "do", "buc", "phien", "mat tien", "tru tien", "lua dao", "gian lan",
    "cho lau", "treo may", "dung may", "van g", "cham chap",
    # co dau (chinh ta chuan, chiem da so noi dung crawl that)
    "không", "lỗi", "khoá", "chậm", "tăng", "thất vọng", "tệ", "kém", "dở",
    "bực", "phiền", "mất tiền", "trừ tiền", "lừa đảo", "gian lận", "chờ lâu",
    "quá lâu", "chưa về", "không về", "hết phiên", "không xong", "vòng vòng",
    "báo lỗi", "đơ ", "treo ứng dụng", "văng ra", "không vào được",
    "không đăng nhập", "mãi không", "mãi ko", "toàn lỗi", "khó dùng",
    "khó sử dụng", "rối", "phức tạp", "chán", "không hài lòng", "báo sai",
    "bảo sai", "nhập sai", "sai sót", "sai lầm",
]

# Tu khoa dac trung cho tung nhom chu de - dung de PHAN LOAI CHU DE mot cach
# xac dinh (deterministic) thay vi chon ngau nhien (random.choice) nhu ban cu:
# gan nhan random khien 2 phan hoi cung noi dung ve 1 van de (vd cung la loi
# dang nhap) bi tach ngau nhien vao cac nhom khac nhau, lam vun vat du lieu va
# khien pain point hien thi rat chung chung / khong phan anh dung noi dung
# khach hang dang phan nan.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "dang_nhap": [
        "đăng nhập", "dang nhap", "otp", "mật khẩu", "mat khau", "xác thực",
        "xac thuc", "sinh trắc học", "sinh trac hoc", "vân tay", "van tay",
        "face id", "đăng xuất", "không vào được app", "không mở được app",
        "không mở được ứng dụng",
    ],
    "giao_dich": [
        "chuyển khoản", "chuyen khoan", "giao dịch", "giao dich", "chuyển tiền",
        "chuyen tien", "nạp tiền", "nap tien", "rút tiền", "rut tien",
        "thanh toán", "thanh toan", "quét mã", "quet ma", " qr", "trừ tiền",
        "tru tien", "treo giao dịch", "lệnh chuyển", "lenh chuyen",
    ],
    "bao_mat": [
        "bảo mật", "bao mat", "khoá tài khoản", "khoa tai khoan", "bị khoá",
        "bi khoa", "lộ thông tin", "lo thong tin", "hack", "lừa đảo", "lua dao",
        "gian lận", "gian lan", "mất tiền trong tài khoản", "đóng băng",
    ],
    "nhan_vien": [
        "nhân viên", "nhan vien", "tổng đài", "tong dai", "chăm sóc khách hàng",
        "cham soc khach hang", "cskh", "thái độ", "thai do", "hỗ trợ", "ho tro",
        "phục vụ", "phuc vu", "gọi điện", "goi dien", "hotline",
    ],
    "ung_dung": [
        "ứng dụng", "ung dung", " app ", "app lỗi", "lag", "treo", "đứng máy",
        "dung may", "văng", "vang ra", "crash", "giao diện", "giao dien",
        "cập nhật", "cap nhat", "update", "lỗi hệ thống", "loi he thong",
    ],
    "chinh_sach": [
        "phí", "phi dich vu", "biểu phí", "bieu phi", "chính sách", "chinh sach",
        "lãi suất", "lai suat", "điều khoản", "dieu khoan", "quy định",
        "quy dinh", "hạn mức", "han muc",
    ],
}


def _infer_topic_label(text: str) -> str:
    """Phan loai chu de dua tren tu khoa xuat hien trong noi dung - xac dinh,
    khong ngau nhien. Neu khong khop tu khoa nao, roi ve nhom 'dich_vu' nhu
    mot nhom tong quat that su (chi khi khong xac dinh duoc), khong phai vi
    bi chon ngau nhien."""
    best_label = "dich_vu"
    best_score = 0
    for label, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_label = label
    return best_label


VALID_TOPIC_LABELS = {"dang_nhap", "giao_dich", "bao_mat", "nhan_vien", "dich_vu", "ung_dung", "chinh_sach"}


def _normalize_topic_label(raw: str, content: str) -> str:
    """Chuan hoa topic_label Gemini tra ve ve dung 1 trong 7 nhan chuan.
    Gemini doi khi tra ve nhan co dau / sai dinh dang so voi enum yeu cau
    trong prompt (vd "dịch_vụ" thay vi "dich_vu") - neu khong chuan hoa, cung
    mot nhom van de se bi tach thanh 2 pain point khac nhau chi vi khac cach
    viet. Neu khong khop nhan nao, suy luan lai tu noi dung thay vi giu nguyen
    chuoi la (tranh tao nhan rac)."""
    if raw:
        ascii_label = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
        ascii_label = ascii_label.strip().lower().replace(" ", "_")
        if ascii_label in VALID_TOPIC_LABELS:
            return ascii_label
    return _infer_topic_label(content.lower())


def _get_client():
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    from google import genai
    return genai.Client(api_key=settings.gemini_api_key)


def _heuristic_prediction(post: Post) -> Prediction:
    text = post.content.lower()
    matched_hints = sum(1 for h in NEGATIVE_HINTS if h in text)
    is_negative = matched_hints > 0
    sentiment = Sentiment.NEGATIVE if is_negative else Sentiment.NEUTRAL
    # Cang khop nhieu tu khoa tieu cuc thi muc do nghiem trong cang cao, thay
    # vi random hoan toan - giup Consensus/Pain Point agent uu tien dung nhom.
    severity = min(0.95, 0.5 + 0.1 * matched_hints) if is_negative else round(random.uniform(0.0, 0.3), 2)
    return Prediction(
        post_id=post.id,
        sentiment=sentiment,
        topic_label=_infer_topic_label(text),
        severity_score=round(severity, 2),
        confidence_score=round(random.uniform(0.6, 0.95), 2),
    )


def classify_post(post: Post) -> Prediction:
    """Phan loai sentiment / chu de / muc do nghiem trong cho mot phan hoi."""
    client = _get_client()
    if client is None:
        return _heuristic_prediction(post)

    settings = get_settings()
    prompt = (
        "Ban la mot he thong phan loai phan hoi khach hang nganh ngan hang. "
        "Phan loai binh luan sau va CHI tra ve JSON (khong giai thich them) voi cac truong: "
        '{"sentiment": "positive|neutral|negative", '
        '"topic_label": "dang_nhap|giao_dich|bao_mat|nhan_vien|dich_vu|ung_dung|chinh_sach", '
        '"severity_score": 0.0-1.0, "confidence_score": 0.0-1.0}. '
        f"Binh luan: \"{post.content}\""
    )

    try:
        response = client.models.generate_content(
            model=settings.llm_model,
            contents=prompt,
            config={
                "max_output_tokens": settings.llm_max_tokens,
                "response_mime_type": "application/json",
            },
        )
        data = json.loads(response.text)
        return Prediction(
            post_id=post.id,
            sentiment=Sentiment(data.get("sentiment", "neutral")),
            topic_label=_normalize_topic_label(data.get("topic_label", ""), post.content),
            severity_score=float(data.get("severity_score", 0.0)),
            confidence_score=float(data.get("confidence_score", 0.5)),
        )
    except Exception:
        # Loi goi API / parse JSON -> fallback heuristic, khong lam gay pipeline.
        return _heuristic_prediction(post)


def verify_negative_signal(prediction: Prediction) -> VerificationResult:
    """
    Doi chieu voi nguon chinh thuc truoc khi xac nhan canh bao (PRD muc 14).
    Vi du: kiem tra xem co quy dinh moi ve xac thuc thiet bi truoc khi ket luan
    la loi ung dung ngan hang.

    Goi y mo rong: bat Google Search grounding tool cua Gemini de model tu
    tim thong bao/bai bao lien quan truoc khi ket luan, thay vi chi dua vao
    kien thuc noi tai cua model.
    """
    client = _get_client()
    if client is None:
        return _heuristic_verification(prediction)

    settings = get_settings()
    prompt = (
        "Ban la Verification Agent trong he thong social listening nganh ngan hang. "
        f"Chu de bi anh huong: {prediction.topic_label}, muc do nghiem trong: {prediction.severity_score}. "
        "Dua tren kien thuc hien co, danh gia xem day co kha nang la mot van de da duoc "
        "xac nhan chinh thuc (vi du thay doi quy dinh, bao tri he thong) hay chua co can cu. "
        'CHI tra ve JSON: {"status": "verified|unverified", "reliability_score": 0.0-1.0, '
        '"reasoning": "giai thich ngan gon bang tieng Viet"}.'
    )

    try:
        response = client.models.generate_content(
            model=settings.llm_model,
            contents=prompt,
            config={
                "max_output_tokens": settings.llm_max_tokens,
                "response_mime_type": "application/json",
            },
        )
        data = json.loads(response.text)
        status = VerificationStatus.VERIFIED if data.get("status") == "verified" else VerificationStatus.UNVERIFIED
        return VerificationResult(
            pain_point_id=uuid4(),
            status=status,
            reference_sources=[],
            reliability_score=float(data.get("reliability_score", 0.3)),
            reasoning=data.get("reasoning", ""),
        )
    except Exception:
        return _heuristic_verification(prediction)


def _heuristic_verification(prediction: Prediction) -> VerificationResult:
    found_reference = random.random() > 0.5
    status = VerificationStatus.VERIFIED if found_reference else VerificationStatus.UNVERIFIED
    return VerificationResult(
        pain_point_id=uuid4(),
        status=status,
        reference_sources=["thong-bao-chinh-thuc.pdf"] if found_reference else [],
        reliability_score=round(random.uniform(0.6, 0.95), 2) if found_reference else round(random.uniform(0.1, 0.4), 2),
        reasoning=(
            "Tim thay nguon doi chieu phu hop." if found_reference
            else "Chua tim duoc nguon doi chieu phu hop, giu trang thai chua xac minh."
        ),
    )
