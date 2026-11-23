"""Decide which brain handles a message.

Roles:
  fast      chit-chat and short factual lookups only
  reasoning default for anything substantive, ambiguous, or a follow-up
  deep      only when asked (/deep): biggest local model, high effort
  research  multi-source research pipeline (/research or "research ...", "look into ...")
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config
    from .ollama_client import OllamaClient

COMMANDS = {"/fast": "fast", "/reason": "reasoning", "/deep": "deep", "/research": "research"}

REASONING_WORDS = {
    "prove", "proof", "derive", "derivation", "integral", "integrate", "differentiate",
    "derivative", "equation", "solve", "theorem", "lemma", "matrix", "eigen", "laplace",
    "fourier", "optimize", "algorithm", "complexity", "debug", "refactor", "implement",
    "code", "function", "python", "c++", "rust", "compile", "stack trace", "traceback",
    "step by step", "explain", "analyze", "analyse", "architecture", "compare", "design",
    "physics", "torque", "stress", "strain", "thermodynamics", "circuit", "firmware", "why",
}
SMALL_TALK = re.compile(
    r"^(hi|hey|hello|yo|sup|what'?s up|whats up|how are you|how'?s it going|good (morning|night|evening)|"
    r"thanks|thank you|thx|ok|okay|cool|nice|lol|bye|gn|what is happen\w*)\b", re.I)
SHORT_FACTUAL = re.compile(
    r"^(what time|what day|what'?s the date|who is|who was|when (is|was|did)|where is|define|"
    r"convert|how many|how much|what is the capital|spell)\b", re.I)
FOLLOWUP = re.compile(
    r"^(more|go on|continue|keep going|and\??|why\??|how so\??|elaborate|expand|deeper|details?|"
    r"(i want|give me|tell me|show me) (some )?more|more (please|details|info)|what else|anything else|"
    r"same (thing|for)|do it again|again|the (first|second|third|last) one)\b", re.I)
RESEARCH = re.compile(
    r"\b(research|look into|deep dive|investigate|find (me )?(sources|websites|sites|papers|articles|links)|"
    r"literature review|gather sources)\b", re.I)
MATH_PATTERN = re.compile(r"(\$[^$]+\$|\\frac|\\int|∫|∑|√|\d+\s*[\^*/]\s*\d+|=\s*\d|\bdx\b|\bdy/dx\b)")
CODE_PATTERN = re.compile(r"(```|\bdef |\bclass |#include|;\s*$|\breturn\b|=>|\{\s*$)", re.M)


@dataclass
class Route:
    role: str               # fast | reasoning | deep | research
    reason: str
    score: int = 0
    followup: bool = False


def parse_command(text: str) -> tuple[str | None, str]:
    """'/fast hello' -> ('fast', 'hello'). Unknown or bare commands return (None, text)."""
    parts = text.strip().split(maxsplit=1)
    if parts and parts[0].lower() in COMMANDS:
        return COMMANDS[parts[0].lower()], (parts[1] if len(parts) > 1 else "")
    return None, text


def is_followup(text: str) -> bool:
    t = text.strip().lower().rstrip("!.? ")
    words = t.split()
    if not words or len(words) > 10:
        return False
    return bool(FOLLOWUP.match(t)) or (len(words) <= 4 and any(w in ("more", "that", "it", "this") for w in words))


def wants_research(text: str) -> bool:
    return len(text.split()) >= 2 and bool(RESEARCH.search(text))


def heuristic_score(text: str, long_chars: int = 700) -> tuple[int, list[str]]:
    """Positive score = needs reasoning."""
    t = text.lower()
    score, why = 0, []
    if CODE_PATTERN.search(text):
        score += 3; why.append("code")
    if MATH_PATTERN.search(text):
        score += 3; why.append("math")
    hits = [w for w in REASONING_WORDS if re.search(rf"\b{re.escape(w)}\b", t)]
    if hits:
        score += min(len(hits), 3) * 2; why.append("keywords:" + ",".join(sorted(hits)[:3]))
    if len(text) > long_chars:
        score += 2; why.append("long")
    return score, why


def route(text: str, cfg: "Config", client: "OllamaClient | None" = None,
          has_history: bool = False) -> Route:
    t = text.strip()
    if wants_research(t):
        return Route("research", "research request")
    if has_history and is_followup(t):
        return Route("reasoning", "follow-up of previous topic", followup=True)
    score, why = heuristic_score(t, cfg.long_prompt_chars)
    if score >= 3:
        return Route("reasoning", "heuristic: " + ", ".join(why), score)
    words = len(t.split())
    if SMALL_TALK.match(t) and words <= 8:
        return Route("fast", "small talk", score)
    if SHORT_FACTUAL.match(t) and words <= 12:
        return Route("fast", "short factual", score)
    # ambiguous -> reasoning (optionally let the fast model decide)
    if cfg.llm_classify and client is not None:
        try:
            msg = client.chat(
                cfg.model_for("fast"),
                [{"role": "system", "content": "Classify the user's request. Reply with exactly one word: FAST "
                  "(greeting, chit-chat, one-line fact) or REASON (anything needing thought, context or detail)."},
                 {"role": "user", "content": t[:2000]}],
                options={"think": False, "temperature": 0, "num_ctx": 2048},
            )
            if (msg.get("content") or "").strip().upper().startswith("FAST"):
                return Route("fast", "llm-classify", score)
            return Route("reasoning", "llm-classify", score)
        except Exception as e:  # classifier failure should never block chat
            return Route("reasoning", f"llm-classify failed ({e.__class__.__name__})", score)
    return Route("reasoning", "ambiguous -> reasoning" + (f" ({', '.join(why)})" if why else ""), score)
