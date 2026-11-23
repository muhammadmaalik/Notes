"""Pick the fast model or the reasoning model for a message.

Heuristic first (free, instant). If it is unsure and llm_classify is on,
ask the fast model for a one-word verdict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config
    from .ollama_client import OllamaClient

REASONING_WORDS = {
    "prove", "proof", "derive", "derivation", "integral", "integrate", "differentiate",
    "derivative", "equation", "solve", "theorem", "lemma", "matrix", "eigen", "laplace",
    "fourier", "optimize", "algorithm", "complexity", "debug", "refactor", "implement",
    "code", "function", "python", "c++", "rust", "compile", "stack trace", "traceback",
    "step by step", "explain why", "analyze", "analyse", "architecture",
    "physics", "torque", "stress", "strain", "thermodynamics", "circuit", "firmware",
}
FAST_WORDS = {"hi", "hello", "hey", "thanks", "thank you", "what time", "remind", "list", "who is", "define"}
MATH_PATTERN = re.compile(r"(\$[^$]+\$|\\frac|\\int|∫|∑|√|\d+\s*[\^*/]\s*\d+|=\s*\d|\bdx\b|\bdy/dx\b)")
CODE_PATTERN = re.compile(r"(```|\bdef |\bclass |#include|;\s*$|\breturn\b|=>|\{\s*$)", re.M)


@dataclass
class Route:
    role: str          # "fast" or "reasoning"
    reason: str
    score: int


def heuristic_score(text: str, long_chars: int = 700) -> tuple[int, list[str]]:
    """Positive score leans reasoning, negative leans fast."""
    t = text.lower()
    score, why = 0, []
    if CODE_PATTERN.search(text):
        score += 3; why.append("code")
    if MATH_PATTERN.search(text):
        score += 3; why.append("math")
    hits = [w for w in REASONING_WORDS if w in t]
    if hits:
        score += min(len(hits), 3) * 2; why.append("keywords:" + ",".join(sorted(hits)[:3]))
    if len(text) > long_chars:
        score += 2; why.append("long")
    if len(text) < 60 and any(t.startswith(w) or t == w for w in FAST_WORDS):
        score -= 3; why.append("small-talk")
    if len(text) < 25 and score == 0:
        score -= 1; why.append("short")
    return score, why


def route(text: str, cfg: "Config", client: "OllamaClient | None" = None) -> Route:
    score, why = heuristic_score(text, cfg.long_prompt_chars)
    if score >= 3:
        return Route("reasoning", "heuristic: " + ", ".join(why), score)
    if score <= -1:
        return Route("fast", "heuristic: " + ", ".join(why), score)
    # unsure zone (0..2)
    if cfg.llm_classify and client is not None:
        try:
            msg = client.chat(
                cfg.model_for("fast"),
                [{"role": "system", "content": "Classify the user's request. Reply with exactly one word: FAST (chat, simple facts, quick tasks) or REASON (math, code, multi-step analysis, planning)."},
                 {"role": "user", "content": text[:2000]}],
                options={"think": False, "temperature": 0, "num_ctx": 2048},
            )
            verdict = (msg.get("content") or "").strip().upper()
            if verdict.startswith("REASON"):
                return Route("reasoning", "llm-classify", score)
            return Route("fast", "llm-classify", score)
        except Exception as e:  # classifier failure should never block chat
            return Route("fast", f"llm-classify failed ({e.__class__.__name__}); default fast", score)
    return Route("fast", "heuristic: default fast" + (" (" + ", ".join(why) + ")" if why else ""), score)
