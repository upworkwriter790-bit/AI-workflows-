"""
Thin wrapper around the Anthropic Messages API.

Design choices:
- Server-side web_search tool (web_search_20250305) is used for Subagents
  2, 3, and 5, which all require CURRENT information (trends, live job
  postings, a recruiter's recent activity). This is a real, hosted tool --
  Anthropic executes the search server-side and returns results already
  merged into the response, so no client-side tool-loop is needed.
- Subagents 1 and 4 (profile audit, resume tailoring) don't need web search
  by default -- they reason over user-supplied text -- so we don't pay for
  search on those calls unless explicitly requested.
- Citations returned by the API (for web-search-grounded claims) are kept
  attached to the raw response so the CLI/API can surface sources under
  job listings and trend claims, per the PRD's "no invented salary/listing"
  requirement.
"""
import logging
import sys
import time

import anthropic

from . import config

logger = logging.getLogger("linkedin_agent.client")


class AgentClient:
    def __init__(self, api_key: str = None, model: str = None):
        config.require_api_key()
        self.client = anthropic.Anthropic(api_key=api_key or config.ANTHROPIC_API_KEY)
        self.model = model or config.DEFAULT_MODEL

    def call(self, system_prompt: str, user_message: str,
              use_web_search: bool = False, max_tokens: int = 4096,
              max_search_uses: int = 8, model: str = None):
        tools = []
        if use_web_search:
            tools.append({
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_search_uses,
            })

        kwargs = dict(
            model=model or self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        if tools:
            kwargs["tools"] = tools

        started = time.monotonic()
        logger.info("anthropic.call.start model=%s web_search=%s", kwargs["model"], use_web_search)
        try:
            response = self.client.messages.create(**kwargs)
        except anthropic.APIError as e:
            logger.error("anthropic.call.error model=%s error=%s", kwargs["model"], e)
            print(f"[error] Anthropic API call failed: {e}", file=sys.stderr)
            raise
        elapsed = time.monotonic() - started
        logger.info("anthropic.call.done model=%s elapsed_s=%.2f", kwargs["model"], elapsed)

        text, sources = self._extract(response)
        return text, sources, response

    @staticmethod
    def _extract(response):
        text_parts = []
        sources = []
        for block in response.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
                # pull citations attached to this text block, if any
                citations = getattr(block, "citations", None) or []
                for c in citations:
                    url = getattr(c, "url", None)
                    title = getattr(c, "title", None)
                    if url:
                        sources.append({"title": title, "url": url})
            elif btype == "web_search_tool_result":
                # Also capture raw search hits even if not directly cited,
                # so we never silently drop a source the model looked at.
                content = getattr(block, "content", None) or []
                for item in content:
                    url = getattr(item, "url", None)
                    title = getattr(item, "title", None)
                    if url:
                        sources.append({"title": title, "url": url})
        # de-dup, preserve order
        seen = set()
        deduped = []
        for s in sources:
            if s["url"] not in seen:
                seen.add(s["url"])
                deduped.append(s)
        return "\n".join(text_parts).strip(), deduped
