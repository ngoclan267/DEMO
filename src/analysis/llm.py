import contextvars
from dataclasses import dataclass
from typing import Any

from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.config import get_settings

# max_retries/timeout bị bound thay vì để mặc định (max_retries=6, timeout=None/vô hạn) — mặc định
# đó khiến 1 lệnh gọi LLM có thể treo NHIỀU PHÚT khi quota Gemini free-tier hết trong ngày (429
# RESOURCE_EXHAUSTED, SDK tự backoff 40-60s mỗi lần x 6 lần). Timeout ngắn để mỗi lệnh gọi fail
# nhanh, nhường lượt cho model kế tiếp trong chuỗi (xem _build_gemini_chain) hoặc fallback OpenAI —
# caller đã có try/except bao quanh nên fail nhanh là an toàn.
_MAX_RETRIES = 1
_TIMEOUT_SECONDS = 20

# RPM (request/phút) THẬT đo trên Google AI Studio free-tier cho từng model (dashboard, 2026-08-16)
# — dùng để tính rate limiter RIÊNG cho mỗi model (xem _rate_limiter_for), vì Google cấp quota TÁCH
# BIỆT theo model: dùng chung 1 con số cho mọi model sẽ throttle SAI (quá chặt hoặc quá lỏng tuỳ
# model). gemma-4-31b-it dùng 7 (không phải 30, RPM ghi trên dashboard) vì TPM thật của nó chỉ
# 16,000/phút — Verification (call nặng nhất, ~2,213 token input trung bình, xem query thật trên
# bảng llm_usage) chạm trần TPM ở khoảng 16,000/2,213 ≈ 7 lượt/phút, SỚM HƠN trần RPM=30 rất nhiều.
# Model không có trong bảng (vd tự thêm sau, quên cập nhật số đo) dùng _UNKNOWN_MODEL_RPM — thận
# trọng thay vì gọi dồn dập ngay từ request đầu.
GEMINI_MODEL_RPM: dict[str, float] = {
    "gemini-3.1-flash-lite": 15,
    "gemma-4-31b-it": 7,
    "gemini-2.5-flash-lite": 10,
    "gemini-3.5-flash": 5,
}
_UNKNOWN_MODEL_RPM = 10.0


def _build_rate_limiter(requests_per_minute: float) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(
        requests_per_second=requests_per_minute / 60,
        check_every_n_seconds=0.1,
        # =1: không cho token tích luỹ lúc rảnh rồi "xả" 1 chùm request khi bận trở lại — luôn cách
        # đều nhau đúng nhịp RPM. Đây chính là lỗ hổng thật đã gây 429: DEFAULT_CONCURRENCY=1 trong
        # runner.py chỉ đảm bảo KHÔNG có 2 request cùng lúc, không đảm bảo KHÔNG có quá N request
        # dồn vào 1 phút — nếu mỗi lượt gọi trả lời nhanh (model nhẹ, prompt ngắn) thì tuần tự vẫn
        # dễ dàng vượt trần RPM (quan sát được trên quota dashboard: RPM vượt trần trong khi TPM/RPD
        # còn dư rất nhiều — đúng dấu hiệu của "gọi đúng số request nhưng gọi quá dồn dập").
        max_bucket_size=1,
    )


# 1 rate limiter RIÊNG cho mỗi cặp (model, api_key) — PHẢI là singleton per-(model, key) (không tạo
# mới mỗi lần gọi) vì rate limiter tự thân có trạng thái (token bucket theo thời gian thực), VÀ vì
# Google cấp quota RIÊNG cho từng (tài khoản Google, model) — 2 key khác nhau gọi CÙNG 1 model có 2
# ngân sách RPM ĐỘC LẬP, dùng chung 1 rate limiter cho cả 2 key sẽ throttle SAI (quá chặt, coi như
# chung 1 quota trong khi thực ra là 2). _build_gemini_client() tạo 1 client MỚI mỗi lần gọi (không
# cache client), nhưng luôn tra lại đúng rate limiter cũ qua cache này, nên giới hạn vẫn có tác dụng
# thật xuyên suốt process dù client là instance mới mỗi lần.
_gemini_rate_limiters: dict[tuple[str, int], InMemoryRateLimiter] = {}
_openai_rate_limiter = _build_rate_limiter(get_settings().openai_rpm_limit)


def _rate_limiter_for(model: str, key_index: int) -> InMemoryRateLimiter:
    cache_key = (model, key_index)
    if cache_key not in _gemini_rate_limiters:
        real_rpm = GEMINI_MODEL_RPM.get(model, _UNKNOWN_MODEL_RPM)
        safe_rpm = real_rpm * get_settings().analysis_rpm_safety_margin
        _gemini_rate_limiters[cache_key] = _build_rate_limiter(safe_rpm)
    return _gemini_rate_limiters[cache_key]


def _parse_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _gemini_api_keys() -> list[str]:
    """gemini_api_key (chính) trước, rồi tới gemini_extra_api_keys (CSV, các tài khoản Google khác)
    — loại bỏ chuỗi rỗng (vd gemini_api_key chưa cấu hình nhưng vẫn có extra key)."""
    settings = get_settings()
    return [k for k in [settings.gemini_api_key, *_parse_csv(settings.gemini_extra_api_keys)] if k]


def _build_gemini_client(model: str, key_index: int, api_key: str, temperature: float) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=temperature,
        max_retries=_MAX_RETRIES,
        timeout=_TIMEOUT_SECONDS,
        rate_limiter=_rate_limiter_for(model, key_index),
    )


def _build_gemini_chain(temperature: float, schema: type | None = None, include_raw: bool = False) -> Runnable:
    """Chuỗi model × api_key LUÂN PHIÊN khi (model, key) đứng trước hết quota (429
    RESOURCE_EXHAUSTED) — primary là settings.analysis_model_name, các model còn lại theo đúng thứ
    tự khai báo trong settings.analysis_fallback_model_names; MỖI model lại luân phiên qua TOÀN BỘ
    api key khai báo (xem _gemini_api_keys) trước khi chuyển sang model kế tiếp — ưu tiên tận dụng
    hết ngân sách của model tốt nhất (trên mọi tài khoản Google) trước khi hạ xuống model yếu hơn.
    Mỗi (model, key) có quota RPM/TPM/RPD RIÊNG trên Google AI Studio (xem GEMINI_MODEL_RPM + comment
    trong config.py) nên đây là dự phòng THẬT — (model, key) kế tiếp còn nguyên quota, khác hẳn retry
    vô ích trên cùng 1 quota đã cạn.

    schema != None: bind with_structured_output(schema) lên TỪNG (model, key) TRƯỚC khi ghép fallback
    (thứ tự ngược lại sẽ lỗi — with_fallbacks() trả về RunnableWithFallbacks, không có method
    with_structured_output)."""
    settings = get_settings()
    model_names = [settings.analysis_model_name, *_parse_csv(settings.analysis_fallback_model_names)]
    api_keys = _gemini_api_keys()
    clients: list[Runnable] = []
    for model in model_names:
        for key_index, api_key in enumerate(api_keys):
            client: Runnable = _build_gemini_client(model, key_index, api_key, temperature)
            if schema is not None:
                client = client.with_structured_output(schema, include_raw=include_raw)
            clients.append(client)
    primary, *rest = clients
    return primary.with_fallbacks(rest) if rest else primary


def _build_fallback(temperature: float) -> ChatOpenAI | None:
    """None nếu openai_api_key trống — chuỗi Gemini/Gemma (xem _build_gemini_chain) vẫn hoạt động
    bình thường, không đổi hành vi."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return ChatOpenAI(
        model=settings.openai_analysis_model_name,
        api_key=settings.openai_api_key,
        temperature=temperature,
        max_retries=_MAX_RETRIES,
        timeout=_TIMEOUT_SECONDS,
        rate_limiter=_openai_rate_limiter,
    )


def get_analysis_llm(temperature: float = 0.0) -> Runnable:
    """LLM dùng cho Consensus/Pain Point Agent (sinh văn bản thuần, đọc qua extract_text) — luân
    phiên qua chuỗi Gemini/Gemma (xem _build_gemini_chain) trước, rồi mới chuyển sang OpenAI
    (fallback) nếu CẢ chuỗi đó lỗi VÀ đã cấu hình OPENAI_API_KEY — dự phòng cho lúc mọi model
    Gemini/Gemma đều hết quota thay vì dừng cả chu kỳ (xem is_quota_error,
    src/pipeline/runner.py's quota_exhausted). Dùng cho lệnh gọi CẦN structured output (Pydantic
    model) thì dùng get_structured_analysis_llm() thay vì tự `.with_structured_output()` lên kết
    quả hàm này — with_fallbacks() trả về RunnableWithFallbacks, không có method
    with_structured_output."""
    primary = _build_gemini_chain(temperature)
    fallback = _build_fallback(temperature)
    return primary if fallback is None else primary.with_fallbacks([fallback])


def get_structured_analysis_llm(schema: type, temperature: float = 0.0, include_raw: bool = False) -> Runnable:
    """Giống get_analysis_llm nhưng cho lệnh gọi cần structured output (Classification/
    Verification Agent) — bind with_structured_output(schema) lên TỪNG model TRƯỚC khi ghép
    fallback (thứ tự ngược lại sẽ lỗi, xem docstring get_analysis_llm).

    include_raw=True: .invoke() trả {"raw": AIMessage, "parsed": schema | None, "parsing_error":
    Exception | None} thay vì thẳng schema — CHỈ dùng khi caller cần đọc usage_metadata (số token,
    xem record_usage) từ "raw". Caller PHẢI tự kiểm tra parsing_error (langchain không tự raise khi
    include_raw=True, khác hành vi mặc định) — xem cách dùng ở classification.py/verification.py."""
    primary = _build_gemini_chain(temperature, schema=schema, include_raw=include_raw)
    fallback = _build_fallback(temperature)
    if fallback is None:
        return primary
    return primary.with_fallbacks([fallback.with_structured_output(schema, include_raw=include_raw)])


def _models_by_family(settings) -> tuple[list[str], list[str]]:
    """Tách danh sách model ĐÃ CẤU HÌNH cho pipeline chính (analysis_model_name +
    analysis_fallback_model_names — đã có RPM đo thật, xem GEMINI_MODEL_RPM) thành 2 họ: Gemini
    (độc quyền) và Gemma (mở) — 2 kiến trúc/quy trình huấn luyện THẬT SỰ khác nhau của Google, dùng
    để Cross-Check Agent chọn model ĐỐI LẬP họ với model đã phân loại lần đầu (xem
    get_cross_check_llm) mà không cần thêm nhà cung cấp/API key mới."""
    all_models = [settings.analysis_model_name, *_parse_csv(settings.analysis_fallback_model_names)]
    gemini_models = [m for m in all_models if m.startswith("gemini-")]
    gemma_models = [m for m in all_models if m.startswith("gemma-")]
    return gemini_models, gemma_models


def get_cross_check_llm(primary_model: str | None, schema: type, temperature: float = 0.0, include_raw: bool = False) -> Runnable | None:
    """LLM DÀNH RIÊNG cho Cross-Check Agent (xem src/analysis/cross_check.py) — CỐ Ý chọn model
    KHÁC HỌ với model đã phân loại lần đầu: `primary_model` bắt đầu bằng "gemini-" thì cross-check
    dùng 1 model họ "gemma-" đã cấu hình (và ngược lại) — Gemini (độc quyền) và Gemma (mở) là 2 kiến
    trúc/quy trình huấn luyện THẬT SỰ khác nhau của Google, không phải cùng 1 model gọi lại 2 lần.
    KHÔNG dùng OpenAI (dự án đã ngừng dùng) — nếu không cấu hình model nào thuộc họ đối lập thì trả
    về None, cross-check coi là không khả dụng, KHÔNG tự ý rơi về OpenAI hay model CÙNG họ.

    `primary_model` None/rỗng (vd không đọc được model đã dùng lần đầu, xem peek_model_for) thì ưu
    tiên họ Gemma trước (miễn phí) nếu có cấu hình, không thì mới dùng Gemini.

    Có fallback luân phiên qua TOÀN BỘ api key đã cấu hình (giống _build_gemini_chain) cho MỌI model
    thuộc họ đối lập, không chỉ 1 model — cross-check cũng cần chống chịu 429 như pipeline chính,
    không thì bản thân cross-check lại trở thành điểm nghẽn quota mới.

    Trả về None nếu không khả dụng — caller PHẢI coi đây là "cross-check không khả dụng", giữ
    nguyên kết luận cũ, KHÔNG chặn pipeline chính (khác hẳn get_analysis_llm/
    get_structured_analysis_llm — cross-check là lớp kiểm tra BỔ SUNG, không phải bước bắt buộc)."""
    settings = get_settings()
    gemini_models, gemma_models = _models_by_family(settings)
    if primary_model and primary_model.startswith("gemini-"):
        target_models = gemma_models
    elif primary_model and primary_model.startswith("gemma-"):
        target_models = gemini_models
    else:
        target_models = gemma_models or gemini_models

    api_keys = _gemini_api_keys()
    if not target_models or not api_keys:
        return None

    clients: list[Runnable] = []
    for model in target_models:
        for key_index, api_key in enumerate(api_keys):
            client: Runnable = _build_gemini_client(model, key_index, api_key, temperature)
            if schema is not None:
                client = client.with_structured_output(schema, include_raw=include_raw)
            clients.append(client)
    primary, *rest = clients
    return primary.with_fallbacks(rest) if rest else primary


@dataclass
class TokenUsage:
    call_type: str
    model: str
    input_tokens: int | None
    output_tokens: int | None


# Ghi nhận usage theo CONTEXTVAR (không phải biến module thường) — tự cô lập theo từng
# thread/task, an toàn khi nhiều post được phân tích song song (xem DEFAULT_CONCURRENCY trong
# src/analysis/runner.py) mà không cần khoá/truyền tham số session xuyên suốt qua
# classification.py/verification.py/consensus.py/pain_point.py (vốn là các hàm THUẦN, chỉ nhận
# content string — không biết gì về DB/topic_id, cố ý giữ nguyên để không phá vỡ interface/test
# hiện có, xem tests/test_analysis/test_runner_persistence.py mock thẳng classify_post/verify_post).
_usage_log: contextvars.ContextVar[list[TokenUsage] | None] = contextvars.ContextVar("_analysis_usage_log", default=None)


def reset_usage_log() -> None:
    """Gọi ở ĐẦU mỗi lượt phân tích 1 post/bài báo, TRƯỚC khi gọi LLM — dọn log cũ (nếu contextvar
    này đang được tái dùng bởi cùng 1 thread cho post trước) để usage không bị lẫn giữa các post."""
    _usage_log.set([])


def pop_usage_log() -> list[TokenUsage]:
    """Lấy toàn bộ usage đã ghi nhận kể từ reset_usage_log() gần nhất, rồi dọn log (tắt tracking
    cho tới lần reset_usage_log() tiếp theo)."""
    log = _usage_log.get() or []
    _usage_log.set(None)
    return log


def peek_model_for(call_type: str) -> str | None:
    """Đọc (KHÔNG xoá) model THẬT đã dùng cho lượt gọi `call_type` gần nhất trong usage log hiện
    tại — khác pop_usage_log() (xoá sạch log, chỉ gọi 1 lần cuối chu kỳ để ghi llm_usage). Dùng để
    Cross-Check Agent biết model đã phân loại lần đầu thuộc họ Gemini hay Gemma mà chọn model đối
    lập (xem get_cross_check_llm trong file này, cross_check_classification trong
    src/analysis/cross_check.py). Trả về None nếu chưa có lượt gọi nào ghi nhận cho call_type này
    (vd chưa reset_usage_log(), hoặc provider không trả usage_metadata)."""
    log = _usage_log.get()
    if not log:
        return None
    for usage in reversed(log):
        if usage.call_type == call_type:
            return usage.model
    return None


def record_usage(call_type: str, message: Any, default_model: str) -> None:
    """Rút usage_metadata (chuẩn LangChain, có ở cả ChatGoogleGenerativeAI lẫn ChatOpenAI) từ 1
    AIMessage rồi thêm vào usage log hiện tại — im lặng bỏ qua nếu không đang track (log=None, vd
    lệnh gọi LLM ở ngoài luồng phân tích chính) hoặc provider không trả usage_metadata (KHÔNG phải
    lỗi — không phải integration nào cũng trả, thiếu số liệu vẫn tốt hơn không ghi nhận gì)."""
    log = _usage_log.get()
    if log is None or message is None:
        return
    usage = getattr(message, "usage_metadata", None)
    if not usage:
        return
    metadata = getattr(message, "response_metadata", None) or {}
    model = metadata.get("model_name") or metadata.get("model") or default_model
    log.append(
        TokenUsage(
            call_type=call_type,
            model=model,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
    )


_QUOTA_ERROR_MARKERS = ("resource_exhausted", "429", "quota")


def is_quota_error(exc: Exception) -> bool:
    """Nhận diện lỗi hết quota (Gemini free-tier RESOURCE_EXHAUSTED/429) từ thông điệp lỗi thay vì
    import đúng class exception của google.api_core — bền hơn qua các version SDK, và không bắt
    buộc thêm dependency trực tiếp chỉ để bắt 1 exception type."""
    message = str(exc).lower()
    return any(marker in message for marker in _QUOTA_ERROR_MARKERS)


def extract_text(content: Any) -> str:
    """`response.content` của Gemini đôi khi là 1 string, đôi khi là list các content block
    dạng {"type": "text", "text": ...} — chuẩn hoá về plain text để lưu DB."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts).strip()
    return str(content).strip()
