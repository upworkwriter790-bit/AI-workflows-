"""LLM backend abstraction + a deterministic heuristic fallback.

Three modes (see config.llm_mode):
  * stub   - no model server; keyword heuristic. Lets the whole pipeline run
             and be tested immediately, and is also the parse-failure fallback.
  * ollama - local models via langchain-ollama (imported lazily).
  * cloud  - OpenAI-compatible via langchain-openai (imported lazily).

Providers expose a single `generate(prompt) -> str`. Higher-level BANT prompt
building and parsing lives in app/bant.py.
"""
from __future__ import annotations

import re
from typing import Dict, List

from app import config
from app.models import ICPConfig, Lead


class LLMError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
class StubProvider:
    mode = "stub"

    def generate(self, prompt: str) -> str:  # pragma: no cover - not used in stub path
        raise LLMError("StubProvider.generate should not be called; use heuristics.")


class OllamaProvider:
    mode = "ollama"

    def __init__(self) -> None:
        from langchain_ollama import ChatOllama  # lazy

        self._llm = ChatOllama(
            model=config.LLM_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            temperature=0.2,
        )

    def generate(self, prompt: str) -> str:
        return self._llm.invoke(prompt).content


class CloudProvider:
    mode = "cloud"

    def __init__(self) -> None:
        from langchain_openai import ChatOpenAI  # lazy

        self._llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            api_key=config.OPENAI_API_KEY,
            temperature=0.2,
        )

    def generate(self, prompt: str) -> str:
        return self._llm.invoke(prompt).content


def get_provider():
    mode = config.llm_mode()
    if mode == "stub":
        return StubProvider()
    if mode == "cloud":
        return CloudProvider()
    return OllamaProvider()


# --------------------------------------------------------------------------- #
# Heuristic BANT scoring (stub backend + parse-failure fallback)
# --------------------------------------------------------------------------- #
_BUDGET_STRONG = ["budget allocated", "allocated budget", "approved budget", "we spend", "per year", "/year", "we pay"]
_BUDGET_MED = ["budget", "pricing", "cost", "roi", "quote", "invest", "$", "usd", "inr", "eur"]
_BUDGET_WEAK = ["find the money", "find budget", "not sure", "depends", "no budget"]

_AUTH_STRONG = ["i approve", "i own", "i decide", "my decision", "i'm the founder", "i am the founder", "ceo", "cfo", "owner", "i sign"]
_AUTH_MED = ["evaluating", "committee", "my team", "we are looking", "recommend", "head", "director", "vp", "manager"]
_AUTH_WEAK = ["check with", "loop in", "my boss", "need sign-off", "need approval", "forward to"]

_NEED_STRONG = ["losing", "lose", "%", "churn", "blocked", "urgent", "critical", "broken", "can't", "cannot", "failing", "per month", "/month"]
_NEED_MED = ["struggle", "problem", "challenge", "inefficient", "manual", "improve", "optimize", "reduce", "slow"]
_NEED_WEAK = ["curious", "just looking", "nice to have", "exploring", "wondering"]

_TIME_STRONG = ["before", "deadline", "by q", "peak season", "contract ends", "expires", "this month", "next week", "black friday", "go live", "launch"]
_TIME_MED = ["this quarter", "next quarter", "soon", "asap", "coming months", "q1", "q2", "q3", "q4"]
_TIME_WEAK = ["someday", "no rush", "sometime", "maybe", "next year", "long term"]


def _score_dim(text: str, strong: List[str], med: List[str], weak: List[str]) -> int:
    t = text.lower()
    if any(k in t for k in strong):
        return 3
    if any(k in t for k in med):
        return 2
    if any(k in t for k in weak):
        return 1
    return 0


def _matched(text: str, keys: List[str]) -> List[str]:
    t = text.lower()
    return [k for k in keys if k in t][:4]


def heuristic_bant(lead: Lead) -> Dict:
    """Return a BANT dict in the same shape the LLM is asked to produce."""
    text = f"{lead.title} {lead.initial_message}"
    br = str(lead.enriched_data.get("budget_range", "")) if lead.enriched_data else ""
    text_budget = f"{text} {br}"

    b = _score_dim(text_budget, _BUDGET_STRONG, _BUDGET_MED, _BUDGET_WEAK)
    a = _score_dim(text, _AUTH_STRONG, _AUTH_MED, _AUTH_WEAK)
    n = _score_dim(text, _NEED_STRONG, _NEED_MED, _NEED_WEAK)
    t = _score_dim(text, _TIME_STRONG, _TIME_MED, _TIME_WEAK)

    # Title signal reinforces authority.
    title = (lead.title or "").lower()
    if any(k in title for k in ["founder", "ceo", "cfo", "owner", "head", "director", "vp", "chief"]):
        a = max(a, 2)

    return {
        "budget": {"score": b, "reasons": ["Heuristic budget read."], "signals": _matched(text_budget, _BUDGET_STRONG + _BUDGET_MED + _BUDGET_WEAK)},
        "authority": {"score": a, "reasons": ["Heuristic authority read from title/message."], "signals": _matched(text, _AUTH_STRONG + _AUTH_MED + _AUTH_WEAK)},
        "need": {"score": n, "reasons": ["Heuristic need read."], "signals": _matched(text, _NEED_STRONG + _NEED_MED + _NEED_WEAK)},
        "timeline": {"score": t, "reasons": ["Heuristic timeline read."], "signals": _matched(text, _TIME_STRONG + _TIME_MED + _TIME_WEAK)},
    }


# --------------------------------------------------------------------------- #
# Heuristic draft (stub backend + fallback)
# --------------------------------------------------------------------------- #
def heuristic_draft(lead: Lead, label: str, next_step: str, questions: List[str]) -> str:
    first = (lead.name or "there").split()[0]
    company = lead.company or "your team"
    q_block = ""
    if questions:
        q_block = "\n\nTo tailor this, could you share:\n" + "\n".join(f"  - {q}" for q in questions)

    if label == "Hot":
        body = (
            f"Hi {first},\n\n"
            f"Thanks for reaching out about {company}. Based on what you shared, this looks like "
            f"a strong fit and I'd love to set up a short intro call to dig into the details.\n\n"
            f"You can grab a time that works here: [MEETING_LINK]{q_block}\n\n"
            f"Talk soon,\nThe Team"
        )
    elif label == "Warm":
        body = (
            f"Hi {first},\n\n"
            f"Thanks for getting in touch. I'd like to understand {company}'s situation a bit better "
            f"so I can point you to the most useful information.{q_block}\n\n"
            f"Looking forward to your reply,\nThe Team"
        )
    else:
        body = (
            f"Hi {first},\n\n"
            f"Thanks for reaching out. Based on what you've described, we may not be the ideal fit right now, "
            f"but I'm happy to share some resources and keep you posted as things evolve.\n\n"
            f"Best,\nThe Team"
        )
    return body


# --------------------------------------------------------------------------- #
# JSON extraction helper for real LLM output
# --------------------------------------------------------------------------- #
def extract_json(text: str) -> str:
    """Pull the first balanced {...} block out of an LLM response."""
    start = text.find("{")
    if start == -1:
        raise LLMError("no JSON object found")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise LLMError("unbalanced JSON braces")
