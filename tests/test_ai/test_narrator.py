"""Tests for AI Narrator — Anthropic, OpenAI, Ollama providers."""

import httpx
import pytest

from obsidian.ai.narrator import Narrator, _DEFAULT_MODELS, _SYSTEM_PROMPTS


# -- Fixtures ----------------------------------------------------------------

@pytest.fixture
def sample_diagnostic() -> dict:
    """Minimal diagnostic dict matching DiagnosticResult.to_dict() shape."""
    return {
        "ticker": "SPY",
        "date": "2025-01-15",
        "regime": "NEU",
        "regime_label": "NEU — Neutral",
        "score_raw": 0.42,
        "score_percentile": 35.0,
        "interpretation": "Normal",
        "z_scores": {"gex": 0.5, "dark_share": -0.3},
        "raw_features": {"gex": 1234567.0, "dark_share": 0.42},
        "baseline_state": "COMPLETE",
        "explanation": "Regime: NEU\nUnusualness: 35.0th percentile",
        "ai_explanation": None,
    }


# -- Anthropic ---------------------------------------------------------------

class TestAnthropicProvider:
    """Tests for Anthropic Messages API integration."""

    @pytest.mark.asyncio
    async def test_happy_path(self, respx_mock, sample_diagnostic):
        """Anthropic returns valid text content."""
        respx_mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={
                "content": [{"type": "text", "text": "SPY shows a neutral regime."}],
            })
        )

        narrator = Narrator(provider="anthropic", api_key="sk-ant-test")
        result = await narrator.narrate(sample_diagnostic)

        assert result == "SPY shows a neutral regime."

    @pytest.mark.asyncio
    async def test_headers(self, respx_mock, sample_diagnostic):
        """Anthropic requests include x-api-key and anthropic-version headers."""
        route = respx_mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={
                "content": [{"type": "text", "text": "ok"}],
            })
        )

        narrator = Narrator(provider="anthropic", api_key="sk-ant-test123")
        await narrator.narrate(sample_diagnostic)

        request = route.calls[0].request
        assert request.headers["x-api-key"] == "sk-ant-test123"
        assert request.headers["anthropic-version"] == "2023-06-01"

    @pytest.mark.asyncio
    async def test_default_model(self, respx_mock, sample_diagnostic):
        """Anthropic uses default model when none specified."""
        route = respx_mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={
                "content": [{"type": "text", "text": "ok"}],
            })
        )

        narrator = Narrator(provider="anthropic", api_key="sk-ant-test")
        await narrator.narrate(sample_diagnostic)

        import json
        body = json.loads(route.calls[0].request.content)
        assert body["model"] == _DEFAULT_MODELS["anthropic"]

    @pytest.mark.asyncio
    async def test_500_error_returns_none(self, respx_mock, sample_diagnostic):
        """Anthropic 500 → graceful None."""
        respx_mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        narrator = Narrator(provider="anthropic", api_key="sk-ant-test")
        result = await narrator.narrate(sample_diagnostic)

        assert result is None

    @pytest.mark.asyncio
    async def test_401_error_returns_none(self, respx_mock, sample_diagnostic):
        """Anthropic 401 (bad key) → graceful None."""
        respx_mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )

        narrator = Narrator(provider="anthropic", api_key="bad-key-123")
        result = await narrator.narrate(sample_diagnostic)

        assert result is None


# -- OpenAI ------------------------------------------------------------------

class TestOpenAIProvider:
    """Tests for OpenAI Chat Completions API integration."""

    @pytest.mark.asyncio
    async def test_happy_path(self, respx_mock, sample_diagnostic):
        """OpenAI returns valid choice content."""
        respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "choices": [{"message": {"content": "SPY is in a neutral microstructure regime."}}],
            })
        )

        narrator = Narrator(provider="openai", api_key="sk-test-openai")
        result = await narrator.narrate(sample_diagnostic)

        assert result == "SPY is in a neutral microstructure regime."

    @pytest.mark.asyncio
    async def test_bearer_header(self, respx_mock, sample_diagnostic):
        """OpenAI requests use Bearer token auth."""
        route = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "choices": [{"message": {"content": "ok"}}],
            })
        )

        narrator = Narrator(provider="openai", api_key="sk-test-key-42")
        await narrator.narrate(sample_diagnostic)

        request = route.calls[0].request
        assert request.headers["Authorization"] == "Bearer sk-test-key-42"

    @pytest.mark.asyncio
    async def test_default_model(self, respx_mock, sample_diagnostic):
        """OpenAI uses default model when none specified."""
        route = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "choices": [{"message": {"content": "ok"}}],
            })
        )

        narrator = Narrator(provider="openai", api_key="sk-test")
        await narrator.narrate(sample_diagnostic)

        import json
        body = json.loads(route.calls[0].request.content)
        assert body["model"] == _DEFAULT_MODELS["openai"]

    @pytest.mark.asyncio
    async def test_500_error_returns_none(self, respx_mock, sample_diagnostic):
        """OpenAI 500 → graceful None."""
        respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        narrator = Narrator(provider="openai", api_key="sk-test")
        result = await narrator.narrate(sample_diagnostic)

        assert result is None


# -- Ollama ------------------------------------------------------------------

class TestOllamaProvider:
    """Tests for Ollama local chat API integration."""

    @pytest.mark.asyncio
    async def test_happy_path(self, respx_mock, sample_diagnostic):
        """Ollama returns valid message content."""
        respx_mock.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(200, json={
                "message": {"role": "assistant", "content": "SPY regime is neutral."},
            })
        )

        narrator = Narrator(provider="ollama")
        result = await narrator.narrate(sample_diagnostic)

        assert result == "SPY regime is neutral."

    @pytest.mark.asyncio
    async def test_no_auth_header(self, respx_mock, sample_diagnostic):
        """Ollama requests have no Authorization or x-api-key headers."""
        route = respx_mock.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(200, json={
                "message": {"content": "ok"},
            })
        )

        narrator = Narrator(provider="ollama")
        await narrator.narrate(sample_diagnostic)

        request = route.calls[0].request
        assert "Authorization" not in request.headers
        assert "x-api-key" not in request.headers

    @pytest.mark.asyncio
    async def test_custom_base_url(self, respx_mock, sample_diagnostic):
        """Ollama uses custom base_url."""
        respx_mock.post("http://gpu-server:11434/api/chat").mock(
            return_value=httpx.Response(200, json={
                "message": {"content": "ok"},
            })
        )

        narrator = Narrator(
            provider="ollama",
            base_url="http://gpu-server:11434",
        )
        result = await narrator.narrate(sample_diagnostic)

        assert result == "ok"

    @pytest.mark.asyncio
    async def test_default_model(self, respx_mock, sample_diagnostic):
        """Ollama uses default model when none specified."""
        route = respx_mock.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(200, json={
                "message": {"content": "ok"},
            })
        )

        narrator = Narrator(provider="ollama")
        await narrator.narrate(sample_diagnostic)

        import json
        body = json.loads(route.calls[0].request.content)
        assert body["model"] == _DEFAULT_MODELS["ollama"]
        assert body["stream"] is False

    @pytest.mark.asyncio
    async def test_connection_error_returns_none(self, respx_mock, sample_diagnostic):
        """Ollama connection failure → graceful None."""
        respx_mock.post("http://localhost:11434/api/chat").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        narrator = Narrator(provider="ollama")
        result = await narrator.narrate(sample_diagnostic)

        assert result is None


# -- Cache -------------------------------------------------------------------

class TestNarratorCache:
    """Tests for in-memory response cache."""

    @pytest.mark.asyncio
    async def test_cache_hit_no_second_call(self, respx_mock, sample_diagnostic):
        """Second call with same input hits cache — no HTTP request."""
        route = respx_mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={
                "content": [{"type": "text", "text": "Cached response."}],
            })
        )

        narrator = Narrator(provider="anthropic", api_key="sk-ant-test")

        result1 = await narrator.narrate(sample_diagnostic)
        result2 = await narrator.narrate(sample_diagnostic)

        assert result1 == "Cached response."
        assert result2 == "Cached response."
        assert route.call_count == 1  # Only one HTTP call

    @pytest.mark.asyncio
    async def test_cache_miss_different_input(self, respx_mock, sample_diagnostic):
        """Different diagnostic dict → cache miss → new HTTP call."""
        route = respx_mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={
                "content": [{"type": "text", "text": "Response."}],
            })
        )

        narrator = Narrator(provider="anthropic", api_key="sk-ant-test")

        await narrator.narrate(sample_diagnostic)

        different = {**sample_diagnostic, "ticker": "QQQ"}
        await narrator.narrate(different)

        assert route.call_count == 2  # Two HTTP calls


# -- Language ----------------------------------------------------------------

class TestLanguage:
    """Tests for language selection in system prompts."""

    @pytest.mark.asyncio
    async def test_hungarian_system_prompt(self, respx_mock, sample_diagnostic):
        """HU language sends Hungarian system prompt."""
        route = respx_mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={
                "content": [{"type": "text", "text": "SPY semleges rezsimben van."}],
            })
        )

        narrator = Narrator(provider="anthropic", api_key="sk-test", language="hu")
        await narrator.narrate(sample_diagnostic)

        import json
        body = json.loads(route.calls[0].request.content)
        assert body["system"] == _SYSTEM_PROMPTS["hu"]

    @pytest.mark.asyncio
    async def test_english_system_prompt(self, respx_mock, sample_diagnostic):
        """EN language sends English system prompt."""
        route = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "choices": [{"message": {"content": "ok"}}],
            })
        )

        narrator = Narrator(provider="openai", api_key="sk-test", language="en")
        await narrator.narrate(sample_diagnostic)

        import json
        body = json.loads(route.calls[0].request.content)
        system_msg = body["messages"][0]
        assert system_msg["role"] == "system"
        assert system_msg["content"] == _SYSTEM_PROMPTS["en"]


# -- Custom Model Override ---------------------------------------------------

class TestCustomModel:
    """Tests for custom model override."""

    @pytest.mark.asyncio
    async def test_custom_model_override(self, respx_mock, sample_diagnostic):
        """Custom model overrides default."""
        route = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "choices": [{"message": {"content": "ok"}}],
            })
        )

        narrator = Narrator(provider="openai", api_key="sk-test", model="gpt-4o-mini")
        await narrator.narrate(sample_diagnostic)

        import json
        body = json.loads(route.calls[0].request.content)
        assert body["model"] == "gpt-4o-mini"


# -- Unknown Provider --------------------------------------------------------

class TestUnknownProvider:
    """Tests for unsupported provider handling."""

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_none(self, sample_diagnostic):
        """Unknown provider → None, no crash."""
        narrator = Narrator(provider="gemini", api_key="test")
        result = await narrator.narrate(sample_diagnostic)

        assert result is None


# -- Empty Response ----------------------------------------------------------

class TestEmptyResponse:
    """Tests for edge cases in API responses."""

    @pytest.mark.asyncio
    async def test_anthropic_empty_content(self, respx_mock, sample_diagnostic):
        """Anthropic returns empty content array → None."""
        respx_mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"content": []})
        )

        narrator = Narrator(provider="anthropic", api_key="sk-test")
        result = await narrator.narrate(sample_diagnostic)

        assert result is None

    @pytest.mark.asyncio
    async def test_openai_empty_choices(self, respx_mock, sample_diagnostic):
        """OpenAI returns empty choices array → None."""
        respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"choices": []})
        )

        narrator = Narrator(provider="openai", api_key="sk-test")
        result = await narrator.narrate(sample_diagnostic)

        assert result is None
