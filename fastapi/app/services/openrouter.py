"""Cliente síncrono de OpenRouter (chat con modelos de respaldo y lista de modelos gratuitos).

Nunca se registra ni se devuelve la clave de la API ni el texto de los mensajes en los errores.
"""
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_RETRY_AFTER_S = 60
DAILY_MARKERS = ("per-day", "per day", "free-models-per-day")


class OpenRouterError(Exception):
    """Fallo al hablar con OpenRouter (red, HTTP, o una respuesta sin contenido)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PerMinuteRateLimit(OpenRouterError):
    """429 por límite por minuto: reintentar después de `retry_after_s` segundos."""

    def __init__(self, retry_after_s: int = DEFAULT_RETRY_AFTER_S):
        super().__init__(f"Límite por minuto de OpenRouter; reintentar en {retry_after_s} s")
        self.retry_after_s = retry_after_s


class DailyLimitReached(OpenRouterError):
    """429 por límite diario de los modelos gratuitos: no hay más hasta `reset_at`."""

    def __init__(self, reset_at: datetime):
        super().__init__(f"Límite diario de OpenRouter alcanzado; se reinicia el {reset_at.isoformat()}")
        self.reset_at = reset_at


@dataclass
class ChatResult:
    content: str
    model: str


def next_utc_midnight(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def _error_message(response: httpx.Response) -> str:
    """El mensaje del cuerpo de error de OpenRouter (`{"error": {"message": …}}`), o el texto crudo recortado."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:300]
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or "")[:300]
    return str(error or "")[:300]


def _reset_header(response: httpx.Response) -> str | None:
    value = response.headers.get("X-RateLimit-Reset")
    if value is None:
        try:  # OpenRouter a veces anida los headers en `error.metadata.headers`
            value = response.json()["error"]["metadata"]["headers"].get("X-RateLimit-Reset")
        except (ValueError, KeyError, TypeError, AttributeError):
            value = None
    return None if value is None else str(value)


def _rate_limit_error(response: httpx.Response) -> OpenRouterError:
    message = _error_message(response)
    haystack = f"{message} {response.text[:2000]}".lower()
    if any(marker in haystack for marker in DAILY_MARKERS):
        reset_at = None
        raw = _reset_header(response)
        if raw:
            try:
                reset_at = datetime.fromtimestamp(int(float(raw)) / 1000, UTC)  # epoch en milisegundos
            except (ValueError, OverflowError, OSError):
                reset_at = None
        return DailyLimitReached(reset_at or next_utc_midnight())
    try:
        retry_after = max(1, int(float(response.headers.get("Retry-After", ""))))
    except ValueError:
        retry_after = DEFAULT_RETRY_AFTER_S
    return PerMinuteRateLimit(retry_after)


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        http: httpx.Client | None = None,
        timeout: float = 90,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=timeout)
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "X-Title": "Pulso Laboral"}

    def _request(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            response = self._http.request(
                method, f"{self._base_url}{path}", headers=self._headers(), timeout=self._timeout, **kw
            )
        except httpx.HTTPError as exc:
            raise OpenRouterError(f"No se pudo conectar con OpenRouter ({type(exc).__name__})") from None
        if response.status_code == 429:
            raise _rate_limit_error(response)
        if response.status_code >= 400:
            raise OpenRouterError(f"OpenRouter respondió {response.status_code}: {_error_message(response)}")
        return response

    def chat(
        self,
        messages: list[dict],
        *,
        model: str,
        fallback_models: list[str] | None = None,
        json_mode: bool = False,
        max_tokens: int = 2000,
    ) -> ChatResult:
        body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2}
        if fallback_models:
            body["models"] = [model, *fallback_models]
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        response = self._request("POST", "/chat/completions", json=body)
        try:
            data = response.json()
        except ValueError:
            raise OpenRouterError("OpenRouter devolvió una respuesta que no es JSON") from None
        if not isinstance(data, dict):
            raise OpenRouterError("OpenRouter devolvió una respuesta inesperada")
        if data.get("error") and not data.get("choices"):  # error con HTTP 200
            code = data["error"].get("code") if isinstance(data["error"], dict) else None
            if code == 429:
                raise _rate_limit_error(response)
            raise OpenRouterError(f"OpenRouter devolvió un error: {str(data['error'])[:300]}")
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise OpenRouterError("OpenRouter no devolvió ninguna respuesta") from None
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterError("El modelo devolvió una respuesta vacía")
        return ChatResult(content=content, model=str(data.get("model") or model))

    def list_free_models(self) -> list[dict]:
        data = self._request("GET", "/models").json().get("data", [])
        return [
            {"id": m["id"], "name": m.get("name") or m["id"], "contextLength": m.get("context_length") or 0}
            for m in data
            if str((m.get("pricing") or {}).get("prompt")) == "0"
            and str((m.get("pricing") or {}).get("completion")) == "0"
        ]


def make_client() -> OpenRouterClient | None:
    """Cliente con la clave del entorno, o None si la IA no está configurada."""
    settings = get_settings()
    if not settings.openrouter_api_key:
        return None
    return OpenRouterClient(settings.openrouter_api_key, base_url=settings.openrouter_base_url)
