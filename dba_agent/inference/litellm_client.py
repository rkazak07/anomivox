"""
LiteLLM Client — LLM Çağrı Katmanı
════════════════════════════════════
LiteLLM proxy üzerinden Ollama modellere erişim sağlar.

Kullanım:
    client = get_llm_client()
    response = await client.chat("Merhaba, CPU kullanımı neden yüksek?")
    
    # Streaming
    async for chunk in client.chat_stream("Analiz et"):
        print(chunk, end="")
"""

import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI, OpenAI

from dba_agent.config import InferenceConfig, get_config

logger = logging.getLogger("dba_agent.inference")


class LLMClient:
    """
    LiteLLM Proxy üzerinden LLM çağrısı yapan client.
    
    Özellikler:
    - Sync ve async desteği
    - Retry + fallback
    - Timeout kontrolü
    - Token sayımı (yaklaşık)
    - Çağrı loglaması
    """

    def __init__(self, config: Optional[InferenceConfig] = None):
        self.config = config or get_config().inference

        # Async client (agent akışında)
        self._async_client = AsyncOpenAI(
            base_url=f"{self.config.litellm_base_url}/v1",
            api_key=self.config.litellm_api_key,
            timeout=self.config.request_timeout,
            max_retries=0,
        )

        # Sync client (basit çağrılarda)
        self._sync_client = OpenAI(
            base_url=f"{self.config.litellm_base_url}/v1",
            api_key=self.config.litellm_api_key,
            timeout=self.config.request_timeout,
            max_retries=0,
        )

        # Fallback client (LiteLLM çalışmazsa doğrudan Ollama)
        self._fallback_client = OpenAI(
            base_url=f"{self.config.ollama_base_url}/v1",
            api_key="ollama",
            timeout=self.config.request_timeout,
            max_retries=0,
        )
        self._async_fallback_client = AsyncOpenAI(
            base_url=f"{self.config.ollama_base_url}/v1",
            api_key="ollama",
            timeout=self.config.request_timeout,
            max_retries=0,
        )

        # İstatistikler
        self._call_count = 0
        self._total_latency = 0.0
        self._error_count = 0

    # ─────────────────────────────────────────
    # Sync API
    # ─────────────────────────────────────────

    def chat(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Senkron LLM çağrısı.
        
        Args:
            prompt: Kullanıcı mesajı
            model: Model adı (varsayılan: reasoning_model)
            system_prompt: System prompt
            messages: Tam mesaj listesi (verilirse prompt/system_prompt yok sayılır)
            temperature: Sıcaklık (varsayılan: config'den)
            max_tokens: Max output token (varsayılan: config'den)
            
        Returns:
            LLM yanıtı (string)
        """
        model = model or self.config.reasoning_model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_output_tokens

        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

        start = time.time()
        self._call_count += 1

        try:
            response = self._sync_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            latency = time.time() - start
            self._total_latency += latency

            result = response.choices[0].message.content or ""
            logger.info(
                f"LLM call: model={model} latency={latency:.1f}s "
                f"tokens={response.usage.total_tokens if response.usage else '?'}"
            )
            return result

        except Exception as e:
            logger.warning(f"LiteLLM failed ({e}), trying direct Ollama fallback...")
            self._error_count += 1
            return self._fallback_chat(model, messages, temperature, max_tokens, **kwargs)

    def _fallback_chat(
        self, model: str, messages: List[Dict], temperature: float,
        max_tokens: int, **kwargs
    ) -> str:
        """LiteLLM çalışmazsa doğrudan Ollama'ya git."""
        # Model adından "ollama/" prefix'ini kaldır
        ollama_model = model.replace("ollama/", "")
        try:
            response = self._fallback_client.chat.completions.create(
                model=ollama_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            result = response.choices[0].message.content or ""
            logger.info(f"Fallback OK: model={ollama_model}")
            return result
        except Exception as e2:
            logger.error(f"Fallback also failed: {e2}")
            raise RuntimeError(
                f"LLM unreachable — LiteLLM: {self.config.litellm_base_url}, "
                f"Ollama: {self.config.ollama_base_url}"
            ) from e2

    # ─────────────────────────────────────────
    # Async API
    # ─────────────────────────────────────────

    async def achat(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Asenkron LLM çağrısı (agent akışında kullanılır)."""
        model = model or self.config.reasoning_model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_output_tokens

        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

        start = time.time()
        self._call_count += 1

        try:
            response = await self._async_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            latency = time.time() - start
            self._total_latency += latency

            result = response.choices[0].message.content or ""
            logger.info(
                f"LLM async call: model={model} latency={latency:.1f}s "
                f"tokens={response.usage.total_tokens if response.usage else '?'}"
            )
            return result

        except Exception as e:
            logger.warning(f"LiteLLM async failed ({e}), trying fallback...")
            self._error_count += 1
            return await self._async_fallback_chat(
                model, messages, temperature, max_tokens, **kwargs
            )

    async def _async_fallback_chat(
        self, model: str, messages: List[Dict], temperature: float,
        max_tokens: int, **kwargs
    ) -> str:
        """Async fallback — doğrudan Ollama."""
        ollama_model = model.replace("ollama/", "")
        try:
            response = await self._async_fallback_client.chat.completions.create(
                model=ollama_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            result = response.choices[0].message.content or ""
            logger.info(f"Async fallback OK: model={ollama_model}")
            return result
        except Exception as e2:
            logger.error(f"Async fallback also failed: {e2}")
            raise RuntimeError(
                f"LLM unreachable — LiteLLM: {self.config.litellm_base_url}, "
                f"Ollama: {self.config.ollama_base_url}"
            ) from e2

    # ─────────────────────────────────────────
    # Streaming API
    # ─────────────────────────────────────────

    async def chat_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Streaming LLM çağrısı — token token döndürür.
        
        async for chunk in client.chat_stream("Analiz et"):
            print(chunk, end="")
        """
        model = model or self.config.reasoning_model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_output_tokens

        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

        try:
            stream = await self._async_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception:
            # Fallback — non-streaming
            logger.warning("Stream failed, falling back to non-streaming")
            result = await self._async_fallback_chat(
                model, messages, temperature, max_tokens, **kwargs
            )
            yield result

    # ─────────────────────────────────────────
    # Yardımcılar
    # ─────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """LLM bağlantı kontrolü."""
        result: Dict[str, Any] = {
            "litellm": False,
            "ollama_direct": False,
            "stats": {
                "total_calls": self._call_count,
                "avg_latency": (
                    self._total_latency / self._call_count
                    if self._call_count > 0
                    else 0
                ),
                "error_count": self._error_count,
            },
        }

        # LiteLLM check
        try:
            models = self._sync_client.models.list()
            result["litellm"] = True
            result["litellm_models"] = [m.id for m in models.data]
        except Exception as e:
            result["litellm_error"] = str(e)

        # Ollama direct check
        try:
            models = self._fallback_client.models.list()
            result["ollama_direct"] = True
            result["ollama_models"] = [m.id for m in models.data]
        except Exception as e:
            result["ollama_error"] = str(e)

        return result

    @property
    def stats(self) -> Dict[str, Any]:
        """Çağrı istatistikleri."""
        return {
            "total_calls": self._call_count,
            "avg_latency_sec": (
                round(self._total_latency / self._call_count, 2)
                if self._call_count > 0
                else 0
            ),
            "error_count": self._error_count,
            "error_rate": (
                round(self._error_count / self._call_count, 2)
                if self._call_count > 0
                else 0
            ),
        }


# ─── Singleton ────────────────────────────────
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Global LLM client singleton."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
