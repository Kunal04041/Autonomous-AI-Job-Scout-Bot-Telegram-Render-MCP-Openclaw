import os
import time
import threading
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    """
    Multi-provider LLM service with thread-safe key-pool rotation and fallback logic.
    Supports Gemini, GitHub Models, Cerebras, Groq, SambaNova, and OpenRouter.
    """

    _cooldowns: Dict[Tuple[str, str], float] = {}
    _lock: threading.Lock = threading.Lock()
    _default_cooldown_seconds: int = 15 * 60

    @classmethod
    def _get_keys(cls, plural_name: str, single_name: str) -> List[str]:
        plural = os.getenv(plural_name, "").strip()
        if plural:
            keys = [k.strip() for k in plural.split(",") if k.strip()]
            if keys:
                return keys
        single = os.getenv(single_name, "").strip()
        return [single] if single else []

    @classmethod
    def _is_available(cls, provider: str, key: str) -> bool:
        with cls._lock:
            return time.time() >= cls._cooldowns.get((provider, key), 0)

    @classmethod
    def _cooldown(cls, provider: str, key: str, seconds: Optional[int] = None) -> None:
        with cls._lock:
            cls._cooldowns[(provider, key)] = time.time() + (seconds or cls._default_cooldown_seconds)

    @staticmethod
    def _messages(prompt: str, system_prompt: str = "") -> list:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _is_rate_error(error_text: str) -> bool:
        triggers = ["rate limit", "quota", "429", "credit", "capacity", "resource_exhausted", "too many"]
        return any(t in error_text for t in triggers)

    @classmethod
    def _try_gemini(cls, prompt: str, system_prompt: str = "", temperature: float = 0) -> Optional[str]:
        import google.generativeai as genai
        from google.generativeai.types import GenerationConfig

        keys = cls._get_keys("GEMINI_API_KEYS", "GEMINI_API_KEY")
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        for key in keys:
            if not cls._is_available("gemini", key):
                continue
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-1.5-flash") # Updated to stable flash
                response = model.generate_content(
                    full_prompt,
                    generation_config=GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=1024,
                    ),
                )
                text = getattr(response, "text", None)
                if text:
                    return text
            except Exception as e:
                print(f"[LLMService] Gemini error: {e}")
                if cls._is_rate_error(str(e).lower()):
                    cls._cooldown("gemini", key)
        return None

    @classmethod
    def _try_github_models(cls, prompt: str, system_prompt: str = "", temperature: float = 0) -> Optional[str]:
        from openai import OpenAI
        keys = cls._get_keys("GITHUB_TOKENS", "GITHUB_TOKEN")
        models = ["gpt-4.1", "gpt-4o"]

        for key in keys:
            if not cls._is_available("github_models", key):
                continue
            for model in models:
                try:
                    client = OpenAI(base_url="https://models.inference.ai.azure.com", api_key=key)
                    response = client.chat.completions.create(
                        model=model,
                        messages=cls._messages(prompt, system_prompt),
                        temperature=temperature,
                        max_tokens=1024,
                    )
                    content = response.choices[0].message.content
                    if content:
                        return content
                except Exception as e:
                    print(f"[LLMService] GitHub ({model}) error: {e}")
                    if cls._is_rate_error(str(e).lower()):
                        cls._cooldown("github_models", key)
                        break
        return None

    @classmethod
    def _try_cerebras(cls, prompt: str, system_prompt: str = "", temperature: float = 0) -> Optional[str]:
        from cerebras.cloud.sdk import Cerebras
        models = ["qwen-3-32b", "llama-3.3-70b"]
        keys = cls._get_keys("CEREBRAS_API_KEYS", "CEREBRAS_API_KEY")

        for key in keys:
            if not cls._is_available("cerebras", key):
                continue
            for model in models:
                try:
                    client = Cerebras(api_key=key)
                    completion = client.chat.completions.create(
                        messages=cls._messages(prompt, system_prompt),
                        model=model,
                        max_completion_tokens=1024,
                        temperature=temperature,
                    )
                    content = completion.choices[0].message.content
                    if content:
                        return content
                except Exception as e:
                    print(f"[LLMService] Cerebras ({model}) error: {e}")
                    if cls._is_rate_error(str(e).lower()):
                        cls._cooldown("cerebras", key)
                        break
        return None

    @classmethod
    def _try_groq(cls, prompt: str, system_prompt: str = "", temperature: float = 0) -> Optional[str]:
        from groq import Groq
        models = ["llama-3.3-70b-versatile", "llama3-8b-8192"]
        keys = cls._get_keys("GROQ_API_KEYS", "GROQ_API_KEY")

        for key in keys:
            if not cls._is_available("groq", key):
                continue
            for model in models:
                try:
                    client = Groq(api_key=key)
                    completion = client.chat.completions.create(
                        model=model,
                        messages=cls._messages(prompt, system_prompt),
                        temperature=temperature,
                        max_tokens=1024,
                    )
                    content = completion.choices[0].message.content
                    if content:
                        return content
                except Exception as e:
                    print(f"[LLMService] Groq ({model}) error: {e}")
                    if cls._is_rate_error(str(e).lower()):
                        cls._cooldown("groq", key)
                        break
        return None

    @classmethod
    def _try_sambanova(cls, prompt: str, system_prompt: str = "", temperature: float = 0) -> Optional[str]:
        from openai import OpenAI
        models = ["Meta-Llama-3.3-70B-Instruct", "Qwen2.5-72B-Instruct"]
        keys = cls._get_keys("SAMBANOVA_API_KEYS", "SAMBANOVA_API_KEY")

        for key in keys:
            if not cls._is_available("sambanova", key):
                continue
            for model in models:
                try:
                    client = OpenAI(base_url="https://api.sambanova.ai/v1", api_key=key)
                    response = client.chat.completions.create(
                        model=model,
                        messages=cls._messages(prompt, system_prompt),
                        temperature=temperature,
                        max_tokens=1024,
                    )
                    content = response.choices[0].message.content
                    if content:
                        return content
                except Exception as e:
                    print(f"[LLMService] SambaNova ({model}) error: {e}")
                    if cls._is_rate_error(str(e).lower()):
                        cls._cooldown("sambanova", key)
                        break
        return None

    @classmethod
    def _try_openrouter(cls, prompt: str, system_prompt: str = "", temperature: float = 0) -> Optional[str]:
        from openai import OpenAI
        models = ["qwen/qwen3-235b-a22b:free", "deepseek/deepseek-r1:free"]
        keys = cls._get_keys("OPENROUTER_API_KEYS", "OPENROUTER_API_KEY")

        for key in keys:
            if not cls._is_available("openrouter", key):
                continue
            for model in models:
                try:
                    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
                    response = client.chat.completions.create(
                        model=model,
                        messages=cls._messages(prompt, system_prompt),
                        temperature=temperature,
                        max_tokens=1024,
                    )
                    content = response.choices[0].message.content
                    if content:
                        return content
                except Exception as e:
                    print(f"[LLMService] OpenRouter ({model}) error: {e}")
                    if cls._is_rate_error(str(e).lower()):
                        cls._cooldown("openrouter", key)
                        break
        return None

    @classmethod
    def call_llm(cls, prompt: str, system_prompt: str = "", temperature: float = 0) -> str:
        for name, fn in [
            ("Gemini", lambda: cls._try_gemini(prompt, system_prompt, temperature)),
            ("GitHub", lambda: cls._try_github_models(prompt, system_prompt, temperature)),
            ("Cerebras", lambda: cls._try_cerebras(prompt, system_prompt, temperature)),
            ("Groq", lambda: cls._try_groq(prompt, system_prompt, temperature)),
            ("SambaNova", lambda: cls._try_sambanova(prompt, system_prompt, temperature)),
            ("OpenRouter", lambda: cls._try_openrouter(prompt, system_prompt, temperature)),
        ]:
            try:
                result = fn()
                if result:
                    return result
            except Exception:
                continue
        return "Error: All LLM providers failed."
