import json
from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.services.openrouter import (
    DailyLimitReached,
    OpenRouterClient,
    OpenRouterError,
    PerMinuteRateLimit,
)

BASE = "https://openrouter.ai/api/v1"
MESSAGES = [{"role": "user", "content": "hola"}]


def _completion(content='{"ok": true}', model="m/uno:free"):
    return httpx.Response(200, json={"model": model, "choices": [{"message": {"content": content}}]})


SATURATED = {"error": {"message": "m/uno:free is temporarily rate-limited upstream. Please retry shortly"}}


@respx.mock
def test_chat_tries_models_in_order_when_saturated():
    route = respx.post(f"{BASE}/chat/completions").mock(
        side_effect=[httpx.Response(429, json=SATURATED), _completion(model="m/dos:free")]
    )
    result = OpenRouterClient("sk-secreta").chat(
        MESSAGES, model="m/uno:free", fallback_models=["m/dos:free", "m/tres:free"], json_mode=True, max_tokens=500
    )
    assert result.content == '{"ok": true}' and result.model == "m/dos:free"
    bodies = [json.loads(c.request.content) for c in route.calls]
    assert [b["model"] for b in bodies] == ["m/uno:free", "m/dos:free"]  # el tercero no hizo falta
    assert bodies[1] == {
        "model": "m/dos:free", "messages": MESSAGES,
        "response_format": {"type": "json_object"}, "max_tokens": 500, "temperature": 0.2,
    }
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer sk-secreta"
    assert request.headers["X-Title"] == "Pulso Laboral"


@respx.mock
def test_chat_other_errors_also_move_to_next_model():
    route = respx.post(f"{BASE}/chat/completions").mock(side_effect=[
        httpx.Response(404, json={"error": {"message": "No endpoints found for m/uno:free"}}),
        _completion(model="m/dos:free"),
    ])
    assert OpenRouterClient("k").chat(MESSAGES, model="m/uno:free", fallback_models=["m/dos:free"]).model == "m/dos:free"
    assert route.call_count == 2


@respx.mock
def test_chat_daily_limit_stops_without_trying_other_models():
    route = respx.post(f"{BASE}/chat/completions").mock(return_value=httpx.Response(
        429, json={"error": {"message": "Rate limit exceeded: free-models-per-day"}}))
    with pytest.raises(DailyLimitReached):
        OpenRouterClient("k").chat(MESSAGES, model="a", fallback_models=["b", "c"])
    assert route.call_count == 1


@respx.mock
def test_chat_all_saturated_raises_per_minute_with_shortest_wait():
    route = respx.post(f"{BASE}/chat/completions").mock(side_effect=[
        httpx.Response(429, json=SATURATED, headers={"Retry-After": "40"}),
        httpx.Response(429, json=SATURATED, headers={"Retry-After": "15"}),
        httpx.Response(500, json={"error": {"message": "boom"}}),
    ])
    with pytest.raises(PerMinuteRateLimit) as exc:
        OpenRouterClient("k").chat(MESSAGES, model="a", fallback_models=["b", "c"])
    assert exc.value.retry_after_s == 15 and "saturados (3 probados)" in str(exc.value)
    assert route.call_count == 3


@respx.mock
def test_chat_without_fallbacks_or_json_mode_omits_those_keys():
    route = respx.post(f"{BASE}/chat/completions").mock(return_value=_completion())
    OpenRouterClient("k").chat(MESSAGES, model="m/uno:free")
    body = json.loads(route.calls.last.request.content)
    assert "models" not in body and "response_format" not in body
    assert body["max_tokens"] == 2000 and body["temperature"] == 0.2


@respx.mock
def test_429_daily_vs_per_minute():
    client = OpenRouterClient("k")
    respx.post(f"{BASE}/chat/completions").mock(return_value=httpx.Response(
        429, json={"error": {"message": "Rate limit exceeded: free-models-per-day"}},
        headers={"X-RateLimit-Reset": "1795046400000"},
    ))
    with pytest.raises(DailyLimitReached) as daily:
        client.chat(MESSAGES, model="m")
    assert daily.value.reset_at == datetime.fromtimestamp(1795046400, UTC)

    respx.post(f"{BASE}/chat/completions").mock(return_value=httpx.Response(
        429, json={"error": {"message": "Rate limit exceeded: free-models-per-min"}}, headers={"Retry-After": "20"},
    ))
    with pytest.raises(PerMinuteRateLimit) as minute:
        client.chat(MESSAGES, model="m")
    assert minute.value.retry_after_s == 20


@respx.mock
def test_429_defaults():
    client = OpenRouterClient("k")
    respx.post(f"{BASE}/chat/completions").mock(return_value=httpx.Response(429, json={"error": {"message": "slow"}}))
    with pytest.raises(PerMinuteRateLimit) as minute:
        client.chat(MESSAGES, model="m")
    assert minute.value.retry_after_s == 60

    respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(429, json={"error": {"message": "Límite PER DAY"}})
    )
    with pytest.raises(DailyLimitReached) as daily:
        client.chat(MESSAGES, model="m")
    reset = daily.value.reset_at  # sin header: las 00:00 UTC siguientes
    assert reset > datetime.now(UTC) and (reset.hour, reset.minute, reset.second) == (0, 0, 0)


@respx.mock
def test_other_errors_raise_openrouter_error_without_leaking_key():
    client = OpenRouterClient("sk-secreta")
    respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(502, json={"error": {"message": "upstream caído"}})
    )
    with pytest.raises(OpenRouterError, match="502") as err:
        client.chat(MESSAGES, model="m")
    assert "sk-secreta" not in str(err.value)

    respx.post(f"{BASE}/chat/completions").mock(side_effect=httpx.ConnectError("sin red"))
    with pytest.raises(OpenRouterError):
        client.chat(MESSAGES, model="m")

    respx.post(f"{BASE}/chat/completions").mock(return_value=_completion(content=""))
    with pytest.raises(OpenRouterError):
        client.chat(MESSAGES, model="m")


@respx.mock
def test_list_free_models_filters_price():
    respx.get(f"{BASE}/models").mock(return_value=httpx.Response(200, json={"data": [
        {"id": "a/gratis:free", "name": "Gratis", "context_length": 65536, "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "b/paga", "name": "Paga", "context_length": 8000, "pricing": {"prompt": "0.000001", "completion": "0.000002"}},
        {"id": "c/mixto", "name": "Mixto", "context_length": 8000, "pricing": {"prompt": "0", "completion": "0.5"}},
        {"id": "d/sin-precio", "name": "Sin precio", "context_length": 8000},
    ]}))
    assert OpenRouterClient("k").list_free_models() == [
        {"id": "a/gratis:free", "name": "Gratis", "contextLength": 65536}
    ]
