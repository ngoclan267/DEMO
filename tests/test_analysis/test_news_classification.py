from unittest.mock import MagicMock, patch

from src.analysis.news_classification import _MAX_CONTENT_CHARS, classify_news_sentiment
from src.analysis.schemas import NewsSentimentResult


def _mock_llm(sentiment: str, *, raw=None):
    """include_raw=True (xem get_structured_analysis_llm) khiến .invoke() trả dict
    {"raw", "parsed", "parsing_error"} thay vì thẳng schema — mock đúng hình dạng đó."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = {
        "raw": raw,
        "parsed": NewsSentimentResult(sentiment=sentiment),
        "parsing_error": None,
    }
    return mock_llm


def test_classify_news_sentiment_returns_llm_result():
    mock_llm = _mock_llm("positive")

    with patch("src.analysis.news_classification.get_structured_analysis_llm", return_value=mock_llm) as mock_get_llm:
        result = classify_news_sentiment("TPBank đạt giải thưởng ngân hàng số", "Nội dung bài báo...")

    assert result.sentiment == "positive"
    mock_get_llm.assert_called_once_with(NewsSentimentResult, include_raw=True)
    mock_llm.invoke.assert_called_once()


def test_classify_news_sentiment_truncates_long_content():
    mock_llm = _mock_llm("neutral")
    long_content = "x" * (_MAX_CONTENT_CHARS + 500)

    with patch("src.analysis.news_classification.get_structured_analysis_llm", return_value=mock_llm):
        classify_news_sentiment("Tiêu đề", long_content)

    prompt = mock_llm.invoke.call_args.args[0]
    assert "x" * _MAX_CONTENT_CHARS in prompt
    assert "x" * (_MAX_CONTENT_CHARS + 1) not in prompt


def test_classify_news_sentiment_includes_title_and_content_in_prompt():
    mock_llm = _mock_llm("negative")

    with patch("src.analysis.news_classification.get_structured_analysis_llm", return_value=mock_llm):
        classify_news_sentiment("TPBank bị khách hàng khiếu nại", "chi tiết sự việc")

    prompt = mock_llm.invoke.call_args.args[0]
    assert "TPBank bị khách hàng khiếu nại" in prompt
    assert "chi tiết sự việc" in prompt


def test_classify_news_sentiment_raises_on_parsing_error():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = {"raw": None, "parsed": None, "parsing_error": ValueError("bad json")}

    with patch("src.analysis.news_classification.get_structured_analysis_llm", return_value=mock_llm):
        try:
            classify_news_sentiment("Tiêu đề", "nội dung")
            raised = False
        except ValueError:
            raised = True
    assert raised


def test_classify_news_sentiment_records_usage_from_raw_message():
    from langchain_core.messages import AIMessage

    raw = AIMessage(content="", usage_metadata={"input_tokens": 120, "output_tokens": 8, "total_tokens": 128})
    mock_llm = _mock_llm("positive", raw=raw)

    with patch("src.analysis.news_classification.get_structured_analysis_llm", return_value=mock_llm):
        from src.analysis.llm import pop_usage_log, reset_usage_log

        reset_usage_log()
        classify_news_sentiment("Tiêu đề", "nội dung")
        usage = pop_usage_log()

    assert len(usage) == 1
    assert usage[0].call_type == "news_sentiment"
    assert usage[0].input_tokens == 120
    assert usage[0].output_tokens == 8
