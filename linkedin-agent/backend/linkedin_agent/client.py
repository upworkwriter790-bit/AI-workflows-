"""
Provider-agnostic LLM client.

AgentClient is a thin facade: every agent module and router.py only ever
calls `.call(system_prompt, user_message, use_web_search=..., ...)` and
gets back `(text, sources, raw_response)`. Which actual provider answers
that call is chosen by config.LLM_PROVIDER, so a whole account being out
of credits/unreachable is a one-line env var fix, not a code change:

  LLM_PROVIDER=anthropic   (default) -- native Anthropic Messages API,
                           full support for the hosted web_search tool.
  LLM_PROVIDER=openrouter  -- OpenAI-compatible API at openrouter.ai.
                           Web search uses OpenRouter's `:online` model
                           suffix (https://openrouter.ai/docs -- web search).
  LLM_PROVIDER=openai      -- native OpenAI Responses API. Web search uses
                           the built-in `web_search_preview` tool.

Citations returned by whichever provider answered are normalized to the
same `[{"title", "url"}, ...]` shape so guardrails.py and the CLI/API
reports don't need to know which backend ran. Web search coverage and
citation format are best-effort per provider -- if a provider's response
doesn't include parseable citations, we return an empty list rather than
guessing, so guardrails.py's "no sources" warning fires honestly instead
of us fabricating a source.
"""
import logging
import sys
import time

from . import config

logger = logging.getLogger("linkedin_agent.client")


class AgentClient:
    def __init__(self, api_key: str = None, model: str = None):
        config.require_api_key()
        self.provider = config.LLM_PROVIDER
        key = api_key or config.configured_api_key()
        backend_model = model or config.DEFAULT_MODEL

        if self.provider == "anthropic":
            self._backend = _AnthropicBackend(key, backend_model)
        elif self.provider == "openrouter":
            self._backend = _OpenRouterBackend(key, backend_model)
        elif self.provider == "openai":
            self._backend = _OpenAIBackend(key, backend_model)
        else:
            raise RuntimeError(f"Unknown LLM_PROVIDER={self.provider!r}")

        self.model = backend_model

    def call(self, system_prompt: str, user_message: str,
              use_web_search: bool = False, max_tokens: int = 4096,
              max_search_uses: int = 8, model: str = None):
        chosen_model = model or self.model
        started = time.monotonic()
        logger.info("llm.call.start provider=%s model=%s web_search=%s",
                     self.provider, chosen_model, use_web_search)
        try:
            text, sources, raw = self._backend.call(
                system_prompt, user_message, use_web_search, max_tokens, max_search_uses, chosen_model
            )
        except Exception as e:
            logger.error("llm.call.error provider=%s model=%s error=%s", self.provider, chosen_model, e)
            print(f"[error] {self.provider} API call failed: {e}", file=sys.stderr)
            raise
        logger.info("llm.call.done provider=%s elapsed_s=%.2f", self.provider, time.monotonic() - started)
        return text, sources, raw


class _AnthropicBackend:
    """Native Anthropic Messages API. Uses the hosted web_search_20250305
    server tool -- Anthropic executes the search server-side and merges
    results into the response, so no client-side tool-loop is needed."""

    def __init__(self, api_key: str, model: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def call(self, system_prompt, user_message, use_web_search, max_tokens, max_search_uses, model):
        tools = []
        if use_web_search:
            tools.append({"type": "web_search_20250305", "name": "web_search", "max_uses": max_search_uses})

        kwargs = dict(model=model, max_tokens=max_tokens, system=system_prompt,
                      messages=[{"role": "user", "content": user_message}])
        if tools:
            kwargs["tools"] = tools

        response = self.client.messages.create(**kwargs)

        text_parts, sources = [], []
        for block in response.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
                for c in getattr(block, "citations", None) or []:
                    url = getattr(c, "url", None)
                    if url:
                        sources.append({"title": getattr(c, "title", None), "url": url})
            elif btype == "web_search_tool_result":
                for item in getattr(block, "content", None) or []:
                    url = getattr(item, "url", None)
                    if url:
                        sources.append({"title": getattr(item, "title", None), "url": url})
        return "\n".join(text_parts).strip(), _dedupe_sources(sources), response


class _OpenRouterBackend:
    """OpenAI-compatible API at openrouter.ai. Routes to whichever
    underlying model you name (e.g. "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o-mini", "meta-llama/llama-3.3-70b-instruct"). Web search
    is enabled via the `:online` model suffix, OpenRouter's web plugin."""

    def __init__(self, api_key: str, model: str):
        import openai
        self.client = openai.OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        self.model = model

    def call(self, system_prompt, user_message, use_web_search, max_tokens, max_search_uses, model):
        chosen_model = model
        if use_web_search and not chosen_model.endswith(":online"):
            chosen_model = f"{chosen_model}:online"

        response = self.client.chat.completions.create(
            model=chosen_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        message = response.choices[0].message
        text = message.content or ""
        sources = []
        try:
            for ann in getattr(message, "annotations", None) or []:
                url_citation = ann.get("url_citation") if isinstance(ann, dict) else getattr(ann, "url_citation", None)
                if not url_citation:
                    continue
                url = url_citation.get("url") if isinstance(url_citation, dict) else getattr(url_citation, "url", None)
                title = url_citation.get("title") if isinstance(url_citation, dict) else getattr(url_citation, "title", None)
                if url:
                    sources.append({"title": title, "url": url})
        except Exception:
            logger.warning("openrouter: could not parse citation annotations, continuing with no sources", exc_info=True)
        return text.strip(), _dedupe_sources(sources), response


class _OpenAIBackend:
    """Native OpenAI Responses API. Web search uses the built-in
    `web_search_preview` tool (requires a search-capable model, e.g.
    gpt-4o / gpt-4o-mini / gpt-4.1)."""

    def __init__(self, api_key: str, model: str):
        import openai
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def call(self, system_prompt, user_message, use_web_search, max_tokens, max_search_uses, model):
        kwargs = dict(model=model, instructions=system_prompt, input=user_message, max_output_tokens=max_tokens)
        if use_web_search:
            kwargs["tools"] = [{"type": "web_search_preview"}]

        response = self.client.responses.create(**kwargs)
        text = getattr(response, "output_text", None) or ""
        sources = []
        try:
            for item in getattr(response, "output", None) or []:
                for content in getattr(item, "content", None) or []:
                    for ann in getattr(content, "annotations", None) or []:
                        url = getattr(ann, "url", None)
                        if url:
                            sources.append({"title": getattr(ann, "title", None), "url": url})
        except Exception:
            logger.warning("openai: could not parse response annotations, continuing with no sources", exc_info=True)
        return text.strip(), _dedupe_sources(sources), response


def _dedupe_sources(sources: list) -> list:
    seen, deduped = set(), []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            deduped.append(s)
    return deduped
