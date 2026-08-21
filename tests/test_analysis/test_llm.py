"""get_analysis_llm/get_structured_analysis_llm — dự phòng OpenAI khi Gemini lỗi/hết quota. Test
thuần (mock cả 2 provider, không gọi API thật) — khác test_llm_integration.py (gọi Gemini thật)."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.analysis.llm import get_analysis_llm, get_structured_analysis_llm
from src.config import Settings


class _DummySchema(BaseModel):
    value: str


def _settings(*, openai_api_key: str, fallback_models: str = "") -> Settings:
    """fallback_models="" (mặc định) tắt luân phiên Gemini/Gemma — CÔ LẬP các test fallback OpenAI
    dưới đây khỏi chuỗi luân phiên (xem các test test_rotates_* ở cuối file), để mock
    ChatGoogleGenerativeAI.invoke 1 lần fail là chạm thẳng OpenAI như test mong đợi, không bị 1
    model Gemini/Gemma dự phòng khác "hứng" trước.

    gemini_extra_api_keys="" PHẢI truyền tường minh (không để Settings tự đọc từ .env thật) — Settings
    đọc .env làm nguồn mặc định cho field không truyền (xem model_config trong src/config.py), nên
    nếu máy chạy test có sẵn GEMINI_EXTRA_API_KEYS thật (nhiều tài khoản Google luân phiên, xem
    src/analysis/llm.py), không cô lập field này sẽ khiến chuỗi luân phiên theo KEY âm thầm bật lên
    dù test chỉ định tắt luân phiên theo MODEL — đúng lỗi từng xảy ra khiến 2 test dưới đây fail chỉ
    vì máy dev có cấu hình nhiều key thật trong .env."""
    return Settings(
        gemini_api_key="fake-gemini-key",
        gemini_extra_api_keys="",
        openai_api_key=openai_api_key,
        openai_analysis_model_name="gpt-4o-mini",
        analysis_model_name="gemini-3.1-flash-lite",
        analysis_fallback_model_names=fallback_models,
    )


def test_returns_plain_gemini_when_no_openai_key():
    with patch("src.analysis.llm.get_settings", return_value=_settings(openai_api_key="")):
        llm = get_analysis_llm()
    assert isinstance(llm, ChatGoogleGenerativeAI)


def test_falls_back_to_openai_when_gemini_fails():
    with patch("src.analysis.llm.get_settings", return_value=_settings(openai_api_key="fake-openai-key")):
        llm = get_analysis_llm()

    fake_response = AIMessage(content="phản hồi từ OpenAI")
    with (
        patch.object(ChatGoogleGenerativeAI, "invoke", side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")),
        patch.object(ChatOpenAI, "invoke", return_value=fake_response) as mock_openai_invoke,
    ):
        result = llm.invoke("prompt bất kỳ")

    assert result.content == "phản hồi từ OpenAI"
    mock_openai_invoke.assert_called_once()


def test_does_not_call_openai_when_gemini_succeeds():
    with patch("src.analysis.llm.get_settings", return_value=_settings(openai_api_key="fake-openai-key")):
        llm = get_analysis_llm()

    fake_response = AIMessage(content="phản hồi từ Gemini")
    with (
        patch.object(ChatGoogleGenerativeAI, "invoke", return_value=fake_response) as mock_gemini_invoke,
        patch.object(ChatOpenAI, "invoke") as mock_openai_invoke,
    ):
        result = llm.invoke("prompt bất kỳ")

    assert result.content == "phản hồi từ Gemini"
    mock_gemini_invoke.assert_called_once()
    mock_openai_invoke.assert_not_called()


def test_raises_when_both_providers_fail():
    with patch("src.analysis.llm.get_settings", return_value=_settings(openai_api_key="fake-openai-key")):
        llm = get_analysis_llm()

    with (
        patch.object(ChatGoogleGenerativeAI, "invoke", side_effect=RuntimeError("429 quota")),
        patch.object(ChatOpenAI, "invoke", side_effect=RuntimeError("429 too many requests")),
        pytest.raises(RuntimeError),
    ):
        llm.invoke("prompt bất kỳ")


def test_structured_output_falls_back_to_openai():
    with patch("src.analysis.llm.get_settings", return_value=_settings(openai_api_key="fake-openai-key")):
        llm = get_structured_analysis_llm(_DummySchema)

    expected = _DummySchema(value="từ OpenAI")
    # with_structured_output() trả về 1 runnable riêng (không phải ChatOpenAI trực tiếp) — mock ở
    # cấp Runnable.invoke chung, đơn giản hơn dò đúng lớp nội bộ langchain sinh ra.
    from langchain_core.runnables.base import RunnableSequence

    with (
        patch.object(ChatGoogleGenerativeAI, "invoke", side_effect=RuntimeError("429 quota")),
        patch.object(RunnableSequence, "invoke", return_value=expected),
    ):
        result = llm.invoke("prompt bất kỳ")

    assert result == expected


def test_structured_output_without_openai_key_has_no_fallback_attr():
    with patch("src.analysis.llm.get_settings", return_value=_settings(openai_api_key="")):
        llm = get_structured_analysis_llm(_DummySchema)
    # Không có OPENAI_API_KEY -> trả thẳng runnable structured-output của Gemini, không bọc fallback.
    assert not hasattr(llm, "fallbacks")


def test_rotates_to_next_gemini_model_when_primary_hits_quota():
    """Model đầu (analysis_model_name) hết quota (429) -> tự chuyển sang model kế tiếp trong
    analysis_fallback_model_names thay vì rơi thẳng xuống OpenAI (hoặc lỗi hẳn nếu không có
    OPENAI_API_KEY)."""
    with patch(
        "src.analysis.llm.get_settings",
        return_value=_settings(openai_api_key="", fallback_models="gemma-4-31b-it"),
    ):
        llm = get_analysis_llm()

    fake_response = AIMessage(content="phản hồi từ model dự phòng")
    call_count = {"n": 0}

    def _invoke_side_effect(self, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return fake_response

    with patch.object(ChatGoogleGenerativeAI, "invoke", autospec=True, side_effect=_invoke_side_effect):
        result = llm.invoke("prompt bất kỳ")

    assert result.content == "phản hồi từ model dự phòng"
    assert call_count["n"] == 2


def test_rotates_through_every_gemini_model_before_openai():
    """Cả 2 model Gemini/Gemma trong chuỗi đều hết quota -> mới rơi xuống OpenAI (không chạm OpenAI
    sớm khi vẫn còn model Gemini/Gemma dự phòng chưa thử)."""
    with patch(
        "src.analysis.llm.get_settings",
        return_value=_settings(openai_api_key="fake-openai-key", fallback_models="gemma-4-31b-it"),
    ):
        llm = get_analysis_llm()

    fake_response = AIMessage(content="phản hồi từ OpenAI")
    with (
        patch.object(ChatGoogleGenerativeAI, "invoke", side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")),
        patch.object(ChatOpenAI, "invoke", return_value=fake_response) as mock_openai_invoke,
    ):
        result = llm.invoke("prompt bất kỳ")

    assert result.content == "phản hồi từ OpenAI"
    mock_openai_invoke.assert_called_once()


def test_gemini_model_rpm_table_has_no_unknown_models_by_default():
    """Mọi model trong cấu hình mặc định (analysis_model_name + analysis_fallback_model_names) đều
    có RPM thật đo được trong GEMINI_MODEL_RPM — tránh âm thầm rơi về _UNKNOWN_MODEL_RPM (thận
    trọng nhưng có thể sai) cho chính các model đang dùng thật."""
    from src.analysis.llm import GEMINI_MODEL_RPM

    settings = _settings(openai_api_key="", fallback_models="gemma-4-31b-it,gemini-2.5-flash-lite,gemini-3.5-flash")
    all_models = [settings.analysis_model_name, *settings.analysis_fallback_model_names.split(",")]
    for model in all_models:
        assert model.strip() in GEMINI_MODEL_RPM, f"Thiếu RPM thật cho model {model!r}"


def test_rate_limiter_is_cached_per_model_and_key_not_shared():
    from src.analysis.llm import _rate_limiter_for

    with patch("src.analysis.llm.get_settings", return_value=_settings(openai_api_key="")):
        a = _rate_limiter_for("gemini-3.1-flash-lite", 0)
        b = _rate_limiter_for("gemini-3.1-flash-lite", 0)
        c = _rate_limiter_for("gemma-4-31b-it", 0)
        d = _rate_limiter_for("gemini-3.1-flash-lite", 1)

    assert a is b
    assert a is not c
    assert a is not d


def test_rotates_across_multiple_api_keys_before_next_model():
    """2 key cho CÙNG 1 model — key đầu hết quota phải thử key thứ 2 (CÙNG model) trước khi rơi
    xuống model dự phòng, không nhảy thẳng sang model khác ngay khi 1 key lỗi."""

    def _settings_with_keys() -> Settings:
        return Settings(
            gemini_api_key="fake-key-1",
            gemini_extra_api_keys="fake-key-2",
            openai_api_key="",
            openai_analysis_model_name="gpt-4o-mini",
            analysis_model_name="gemini-3.1-flash-lite",
            analysis_fallback_model_names="",
        )

    with patch("src.analysis.llm.get_settings", return_value=_settings_with_keys()):
        llm = get_analysis_llm()

    fake_response = AIMessage(content="phản hồi từ key thứ 2")
    seen_keys: list[str] = []

    def _invoke_side_effect(self, *args, **kwargs):
        seen_keys.append(self.google_api_key.get_secret_value() if hasattr(self.google_api_key, "get_secret_value") else self.google_api_key)
        if len(seen_keys) == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return fake_response

    with patch.object(ChatGoogleGenerativeAI, "invoke", autospec=True, side_effect=_invoke_side_effect):
        result = llm.invoke("prompt bất kỳ")

    assert result.content == "phản hồi từ key thứ 2"
    assert len(seen_keys) == 2
