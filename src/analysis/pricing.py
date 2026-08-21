"""Bảng giá THAM KHẢO để ước tính chi phí LLM theo số token đã dùng (xem src/db/models.py::LLMUsage)
— KHÔNG phải số tiền thật đã bị trừ (Gemini hiện đang dùng ở free-tier — xem src/analysis/llm.py),
chỉ là ước tính theo bảng giá công khai của nhà cung cấp. Giá thay đổi theo thời gian — cập nhật lại
PRICING_USD_PER_1M_TOKENS khi đổi model hoặc khi nhà cung cấp đổi giá, đừng coi đây là nguồn giá cố
định vĩnh viễn."""

from dataclasses import dataclass


@dataclass
class ModelPricing:
    input_usd_per_1m: float
    output_usd_per_1m: float


# USD / 1 triệu token. Chỉ liệt kê model đã XÁC NHẬN giá thật — model lạ/chưa liệt kê trả về None ở
# estimate_cost_usd() (không đoán bừa 1 con số), không mặc định coi là 0 hay áp giá của model khác.
PRICING_USD_PER_1M_TOKENS: dict[str, ModelPricing] = {
    "gpt-4o-mini": ModelPricing(input_usd_per_1m=0.15, output_usd_per_1m=0.60),
}

# Gemma (tiền tố "gemma-") được Google phục vụ MIỄN PHÍ qua Gemini API (model mở, không tính phí kể
# cả ngoài free-tier) — khác hẳn các model "gemini-*" độc quyền có giá riêng theo từng phiên bản.
_FREE_MODEL_PREFIXES = ("gemma-",)


def estimate_cost_usd(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """None nghĩa là KHÔNG RÕ GIÁ (model chưa có trong bảng, hoặc thiếu số token) — cố ý khác 0.0
    (biết chắc là miễn phí, vd Gemma) để giao diện không hiển thị nhầm "miễn phí" cho model chưa
    xác nhận được giá thật."""
    if input_tokens is None or output_tokens is None:
        return None
    if any(model.startswith(prefix) for prefix in _FREE_MODEL_PREFIXES):
        return 0.0
    pricing = PRICING_USD_PER_1M_TOKENS.get(model)
    if pricing is None:
        return None
    return (input_tokens / 1_000_000) * pricing.input_usd_per_1m + (output_tokens / 1_000_000) * pricing.output_usd_per_1m
