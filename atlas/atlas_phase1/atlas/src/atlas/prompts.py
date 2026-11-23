"""System prompt assembly: identity + user profile + time + memories + context hints."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

BASE = """You are Atlas, a personal AI assistant running locally on the user's own computers.
You are talking to {call_me}. Address them as {call_me} when it is natural (not every message).

How to answer:
- Lead with the answer. Be concise and direct; expand only when the question needs depth.
- Engineering/physics depth is welcome: real numbers, units, equations, and named sources.
- Do NOT reply with a list of clarifying questions. If a request is vague, make the most reasonable
  interpretation from the conversation and memories, answer it, and offer one short follow-up option.
- Short follow-ups ("more", "go on", "why?", "what about the second one") refer to the previous topic.
- Use tools when they clearly help: web_search for current facts, fetch_url to actually read a page,
  deadlines_* for tasks, read_file/list_dir for local files. Do not invent URLs, numbers or quotes.
- If you are unsure, say so briefly. Never claim to have done something you did not do.
- You cannot delete files, run sudo, or send messages; say so if asked."""


def now_line(tz: str) -> str:
    now = datetime.now(ZoneInfo(tz))
    return f"Current date and time: {now.strftime('%A, %B %d, %Y, %I:%M %p')} ({tz}, UTC{now.strftime('%z')[:3]})."


def build_system_prompt(*, call_me: str, profile_text: str, tz: str, facts: list[str] | None = None,
                        topic_hint: str | None = None, extra: str = "") -> str:
    parts = [BASE.format(call_me=call_me or "the user"), now_line(tz)]
    if profile_text:
        parts.append("About the user (from their profile):\n" + profile_text)
    if facts:
        parts.append("Things you remember about the user (from earlier conversations):\n"
                     + "\n".join(f"- {f}" for f in facts))
    if topic_hint:
        parts.append(f"The user's latest message is a follow-up. The current topic is: {topic_hint}. "
                     "Continue that topic with new, deeper information; do not repeat what you already said.")
    if extra:
        parts.append(extra.strip())
    return "\n\n".join(parts)
