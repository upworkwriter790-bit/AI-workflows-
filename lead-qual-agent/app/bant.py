"""BANT qualification engine.

The LLM (or heuristic) interprets the lead text into 0-3 BANT dimension scores.
This module computes the ICP fit score, applies per-client weights, thresholds
and hard rules in code, and produces an auditable QualificationResult.
"""
from __future__ import annotations

import json
from typing import Dict, List, Tuple

from app import llm as llm_mod
from app.config import llm_mode
from app.models import (
    BANTConfig,
    BANTDimension,
    ICPConfig,
    Label,
    Lead,
    NextStep,
    QualificationResult,
)

# The 13 strategic BANT questions guide what the model should look for.
QUALIFICATION_GUIDE = """\
Budget  - Is money allocated or realistically available? (strong: "allocated this quarter",
          "we spend X/year"; weak: "we'd have to find the money")
Authority - Is the contact a decision-maker, influencer, or end user? Who else is involved?
          (strong: economic buyer / "I approve this"; weak: "I'll loop in my boss")
Need    - Is there a real, quantified, urgent pain? (strong: "we lose 15%/month", "this blocks Q4";
          weak: "nice to have")
Timeline - Is there a real deadline or event driving action? (strong: "live before peak season",
          "contract ends 31 Dec"; weak: "sometime maybe")
"""


# --------------------------------------------------------------------------- #
# ICP fit (deterministic, computed in code -> auditable)
# --------------------------------------------------------------------------- #
def compute_fit_score(lead: Lead, icp: ICPConfig) -> Tuple[int, Dict[str, bool]]:
    enr = lead.enriched_data or {}
    industry = (enr.get("industry", "") or "").lower()
    size = enr.get("company_size")
    region = (enr.get("region", "") or "").upper()
    title = (lead.title or "").lower()

    signals: Dict[str, bool] = {}

    # Industry (include/exclude)
    inc = [i.lower() for i in icp.target_industries]
    exc = [i.lower() for i in icp.exclude_industries]
    if exc and any(e in industry for e in exc if industry):
        signals["industry_match"] = False
    elif not inc:
        signals["industry_match"] = True
    else:
        signals["industry_match"] = bool(industry) and any(i in industry for i in inc)

    # Company size
    if isinstance(size, int):
        signals["company_size_match"] = icp.company_size_min <= size <= icp.company_size_max
    else:
        signals["company_size_match"] = False  # unknown = not a positive signal

    # Region
    if not icp.target_regions:
        signals["region_match"] = True
    else:
        signals["region_match"] = bool(region) and region in [r.upper() for r in icp.target_regions]

    # Title
    if not icp.target_titles:
        signals["title_match"] = True
    else:
        signals["title_match"] = any(t.lower() in title for t in icp.target_titles)

    # Use-case keyword overlap with the lead message
    msg = (lead.initial_message or "").lower()
    signals["use_case_match"] = any(uc.lower() in msg for uc in icp.ideal_use_cases) if icp.ideal_use_cases else False

    weights = {
        "industry_match": 25,
        "company_size_match": 20,
        "region_match": 15,
        "title_match": 20,
        "use_case_match": 20,
    }
    score = sum(w for key, w in weights.items() if signals.get(key))
    return min(100, score), signals


# --------------------------------------------------------------------------- #
# Weighted BANT + rules
# --------------------------------------------------------------------------- #
def weighted_bant(dims: Dict[str, int], weights: Dict[str, float]) -> float:
    """Return normalized 0..1 weighted BANT score (max raw = 3 * sum(weights))."""
    total_w = sum(weights.get(d, 0) for d in ("budget", "authority", "need", "timeline")) or 1.0
    raw = sum(dims.get(d, 0) * weights.get(d, 0) for d in ("budget", "authority", "need", "timeline"))
    return round(raw / (3.0 * total_w), 4)


def apply_rules(dims: Dict[str, int], total_0_1: float, cfg: BANTConfig) -> Tuple[Label, NextStep]:
    thr = cfg.score_thresholds
    rules = cfg.rules

    # Base label from thresholds
    if total_0_1 >= thr.get("hot_min", 0.70):
        label = Label.hot
    elif total_0_1 >= thr.get("warm_min", 0.40):
        label = Label.warm
    else:
        label = Label.cold

    # Hard rules
    if rules.get("auto_disqualify_if_need_0") and dims.get("need", 0) == 0:
        label = Label.cold
    if rules.get("require_authority_ge_1") and dims.get("authority", 0) == 0 and label == Label.hot:
        label = Label.warm  # can't be Hot without at least an influencer

    next_step = {
        Label.hot: NextStep.book_meeting,
        Label.warm: NextStep.nurture,
        Label.cold: NextStep.disqualify if dims.get("need", 0) == 0 else NextStep.nurture,
    }[label]
    return label, next_step


# --------------------------------------------------------------------------- #
# Prompt building
# --------------------------------------------------------------------------- #
def build_prompt(lead: Lead, icp: ICPConfig, rag_context: str) -> str:
    enr = lead.enriched_data or {}
    return (
        "You are a B2B sales qualification expert. Score this lead on BANT.\n\n"
        "LEAD\n"
        f"- Name: {lead.name}\n"
        f"- Company: {lead.company}\n"
        f"- Title: {lead.title}\n"
        f"- Industry: {enr.get('industry', 'unknown')}\n"
        f"- Company size: {enr.get('company_size', 'unknown')}\n"
        f"- Region: {enr.get('region', 'unknown')}\n"
        f"- Budget range: {enr.get('budget_range', 'unknown')}\n"
        f"- Message: {lead.initial_message}\n\n"
        "QUALIFICATION GUIDE\n"
        f"{QUALIFICATION_GUIDE}\n"
        "ICP & PLAYBOOK CONTEXT (from retrieval)\n"
        f"{rag_context or '(none provided)'}\n\n"
        "For each BANT dimension give a score 0-3, 1-2 short reasons, and key signal phrases.\n"
        "Respond with ONLY valid JSON in exactly this schema:\n"
        "{\n"
        '  "budget":    {"score": 0, "reasons": ["..."], "signals": ["..."]},\n'
        '  "authority": {"score": 0, "reasons": ["..."], "signals": ["..."]},\n'
        '  "need":      {"score": 0, "reasons": ["..."], "signals": ["..."]},\n'
        '  "timeline":  {"score": 0, "reasons": ["..."], "signals": ["..."]},\n'
        '  "reasoning": "2-4 sentence summary"\n'
        "}\n"
    )


def _dims_from_raw(raw: Dict) -> Dict[str, BANTDimension]:
    out = {}
    for d in ("budget", "authority", "need", "timeline"):
        node = raw.get(d, {}) or {}
        score = int(node.get("score", 0))
        score = max(0, min(3, score))
        out[d] = BANTDimension(
            score=score,
            reasons=list(node.get("reasons", []))[:3],
            signals=list(node.get("signals", []))[:5],
        )
    return out


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def qualify(lead: Lead, icp: ICPConfig, cfg: BANTConfig, rag_context: str) -> QualificationResult:
    mode = llm_mode()
    provider = llm_mod.get_provider()
    reasoning = ""
    method = "rule_based"

    if mode == "stub":
        raw = llm_mod.heuristic_bant(lead)
        method = "rule_based"
    else:
        try:
            out = provider.generate(build_prompt(lead, icp, rag_context))
            raw = json.loads(llm_mod.extract_json(out))
            reasoning = str(raw.get("reasoning", ""))
            method = "llm+rules"
        except Exception:
            raw = llm_mod.heuristic_bant(lead)
            reasoning = "LLM parse failed; used heuristic fallback."
            method = "rule_based(fallback)"

    dims = _dims_from_raw(raw)
    dim_scores = {d: dims[d].score for d in dims}

    fit_score, fit_signals = compute_fit_score(lead, icp)
    bant_0_1 = weighted_bant(dim_scores, cfg.weights)
    intent_score = round(bant_0_1 * 100)

    total_0_1 = round(cfg.fit_weight * (fit_score / 100.0) + cfg.bant_weight * bant_0_1, 4)
    total_score = round(total_0_1 * 100)

    label, next_step = apply_rules(dim_scores, total_0_1, cfg)

    if not reasoning:
        reasoning = (
            f"ICP fit {fit_score}/100 ({sum(1 for v in fit_signals.values() if v)}/{len(fit_signals)} signals). "
            f"BANT B{dim_scores['budget']} A{dim_scores['authority']} "
            f"N{dim_scores['need']} T{dim_scores['timeline']} -> intent {intent_score}/100. "
            f"Classified {label.value}."
        )

    return QualificationResult(
        lead_id=lead.id,
        client_id=lead.client_id,
        budget=dims["budget"],
        authority=dims["authority"],
        need=dims["need"],
        timeline=dims["timeline"],
        fit_score=fit_score,
        intent_score=intent_score,
        total_score=total_score,
        label=label,
        next_step=next_step,
        reasoning=reasoning,
        scoring_method=method,
    )


# --------------------------------------------------------------------------- #
# Response drafting
# --------------------------------------------------------------------------- #
def draft_followup_questions(qual: QualificationResult) -> List[str]:
    """Ask 1-3 focused questions for the weakest, most decision-relevant gaps."""
    gaps = []
    if qual.budget.score <= 1:
        gaps.append(("budget", "Is there a budget set aside for solving this, or is that part of what we'd scope together?"))
    if qual.authority.score <= 1:
        gaps.append(("authority", "Besides yourself, who else would be involved in a decision like this?"))
    if qual.need.score <= 1:
        gaps.append(("need", "What's the impact on the business if this problem isn't solved?"))
    if qual.timeline.score <= 1:
        gaps.append(("timeline", "When are you hoping to have this live?"))
    # Prioritise need/timeline, then authority, then budget; cap at 3.
    order = {"need": 0, "timeline": 1, "authority": 2, "budget": 3}
    gaps.sort(key=lambda g: order[g[0]])
    return [q for _, q in gaps[:3]]


def draft_response(lead: Lead, qual: QualificationResult, rag_context: str) -> str:
    mode = llm_mode()
    questions = draft_followup_questions(qual)

    if mode == "stub":
        return llm_mod.heuristic_draft(lead, qual.label.value, qual.next_step.value, questions)

    provider = llm_mod.get_provider()
    if qual.label == Label.hot:
        action = "Propose a short intro call and include the placeholder [MEETING_LINK]. Ask at most 1-2 brief clarifying questions."
    elif qual.label == Label.warm:
        action = "Provide a helpful, concise reply and ask 2-3 discovery questions to understand budget, authority, need and timeline."
    else:
        action = "Politely share basic info, indicate we may not be the best fit right now, and offer to stay in touch."

    prompt = (
        "You are a helpful B2B sales assistant drafting the first reply to an inbound lead.\n"
        "Be friendly, concise, professional, and personalize using their name, company and stated pain.\n"
        "Ground any claims in the context; do not invent facts about their company.\n\n"
        f"ACTION: {action}\n\n"
        f"LEAD MESSAGE:\n{lead.initial_message}\n\n"
        f"QUALIFICATION: label={qual.label.value}, reasoning={qual.reasoning}\n"
        f"SUGGESTED QUESTIONS: {questions}\n\n"
        f"CONTEXT (playbook / tone):\n{rag_context or '(none)'}\n\n"
        "Write only the message body (email/WhatsApp). No JSON, no meta commentary."
    )
    try:
        return provider.generate(prompt)
    except Exception:
        return llm_mod.heuristic_draft(lead, qual.label.value, qual.next_step.value, questions)
