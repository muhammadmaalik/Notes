"""Atlas agent: commands -> route -> (research | chat with tools) -> memory."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .config import Config
from .facts import FactMemory
from .memory import Memory
from .ollama_client import ClientPool
from .profile import load_profile, render_profile, user_timezone
from .prompts import build_system_prompt
from .research import Researcher
from .router import Route, is_followup, parse_command, route
from .tools.registry import ToolRegistry

TokenFn = Callable[[str], None]


@dataclass
class Callbacks:
    on_token: TokenFn | None = None       # streamed answer text
    on_thinking: TokenFn | None = None    # streamed reasoning text (if the model thinks)
    on_event: TokenFn | None = None       # progress lines ("search: ...", "read [3] ...")


@dataclass
class Reply:
    text: str
    role: str
    model: str
    route_reason: str
    tool_calls: list[str] = field(default_factory=list)
    report_path: str | None = None
    streamed: bool = False


class Atlas:
    def __init__(self, cfg: Config, pool: ClientPool, memory: Memory, tools: ToolRegistry,
                 researcher: Researcher | None = None):
        self.cfg, self.pool, self.memory, self.tools = cfg, pool, memory, tools
        self.profile = load_profile(cfg.profile_path)
        self.call_me = str(self.profile.get("call_me") or self.profile.get("name") or "the user")
        self.tz = user_timezone(self.profile)
        self.profile_text = render_profile(self.profile)
        self.facts = FactMemory(cfg, pool, memory)
        self.researcher = researcher or Researcher(cfg, pool, call_me=self.call_me, tz=self.tz)

    # ------------------------------------------------------------------ public
    def ask(self, conversation_id: int, text: str, force_role: str | None = None,
            cb: Callbacks | None = None, background: bool = True) -> Reply:
        cb = cb or Callbacks()
        text = text.strip()

        special = self._memory_command(text)
        if special is not None:
            return special

        cmd_role, rest = parse_command(text)
        if cmd_role:
            text = rest.strip()
            if not text and cmd_role != "research":
                return Reply(f"Usage: /{cmd_role if cmd_role != 'reasoning' else 'reason'} <message>",
                             cmd_role, "", "usage")
        has_history = bool(self.memory.history(conversation_id, limit=2))
        role = cmd_role or force_role
        if role:
            r = Route(role, "command" if cmd_role else "forced by user",
                      followup=has_history and is_followup(text))
        else:
            r = route(text, self.cfg, self.pool.for_role("fast"), has_history=has_history)

        last = self.memory.last_assistant(conversation_id) if has_history else None
        if r.role == "research" or (r.followup and last and last.get("route") == "research"):
            return self._research(conversation_id, text, r, cb, background)
        return self._chat(conversation_id, text, r, cb, background)

    def wait_background(self, timeout: float = 60) -> None:
        self.facts.wait(timeout)

    # ------------------------------------------------------------------ memory commands
    def _memory_command(self, text: str) -> Reply | None:
        low = text.lower()
        if low.startswith("/remember"):
            fact = text[len("/remember"):].strip()
            if not fact:
                return Reply("Usage: /remember <fact about you>", "memory", "", "command")
            fid = self.facts.remember(fact, source="user")
            msg = f"Saved to memory (#{fid}): {fact}" if fid else "Already known (or not allowed to store)."
            return Reply(msg, "memory", "", "command")
        if low.startswith("/forget"):
            what = text[len("/forget"):].strip()
            if not what:
                return Reply("Usage: /forget <id or text>", "memory", "", "command")
            gone = self.facts.forget(what)
            msg = ("Forgot:\n" + "\n".join(f"- {g}" for g in gone)) if gone else "No matching memory found."
            return Reply(msg, "memory", "", "command")
        if low in ("/memory", "/memories"):
            facts = self.memory.list_facts()
            msg = "\n".join(f"#{f['id']} {f['text']}" for f in facts) or "No memories yet."
            return Reply(msg, "memory", "", "command")
        return None

    # ------------------------------------------------------------------ chat
    def _chat(self, cid: int, text: str, r: Route, cb: Callbacks, background: bool) -> Reply:
        role = r.role
        model = self.cfg.model_for(role)
        client = self.pool.for_role(role)
        options = self.cfg.options_for(role)

        if cb.on_event:
            cb.on_event(f"route: {role} · {model} · {r.reason}")
        if role == "deep" and self.cfg.deep_unload_fast and self.cfg.host_for("fast") != self.cfg.host_for("deep"):
            self.pool.for_role("fast").unload(self.cfg.model_for("fast"))

        facts = self.facts.relevant(text) if self.cfg.memory.get("enabled", True) else []
        topic_hint = self.memory.last_topic(cid) if r.followup else None
        system = build_system_prompt(call_me=self.call_me, profile_text=self.profile_text, tz=self.tz,
                                     facts=facts, topic_hint=topic_hint, extra=self.cfg.system_prompt)
        turns = int(self.cfg.memory.get("history_turns", 10)) * 2
        messages = [{"role": "system", "content": system}, *self.memory.history(cid, limit=turns),
                    {"role": "user", "content": text}]
        self.memory.add_message(cid, "user", text, route=role)

        called: list[str] = []
        final, streamed = "", False
        for _ in range(self.cfg.max_tool_steps + 1):
            if cb.on_token:
                msg = client.chat_collect(model, messages, tools=self.tools.schemas(), options=options,
                                          on_token=cb.on_token, on_thinking=cb.on_thinking)
                streamed = streamed or bool(msg.get("content"))
            else:
                msg = client.chat(model, messages, tools=self.tools.schemas(), options=options)
            calls = msg.get("tool_calls") or []
            if not calls:
                final = (msg.get("content") or "").strip()
                break
            assistant = {"role": "assistant", "content": msg.get("content", ""), "tool_calls": calls}
            if msg.get("thinking"):
                assistant["thinking"] = msg["thinking"]
            messages.append(assistant)
            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                if cb.on_event:
                    cb.on_event(f"tool: {name} {fn.get('arguments') or ''}")
                result = self.tools.call(name, fn.get("arguments") or {})
                called.append(name)
                messages.append({"role": "tool", "tool_name": name, "content": result})
        else:
            final = "I hit the tool-step limit before finishing. Try a narrower request."
            streamed = False

        self.memory.add_message(cid, "assistant", final, model=model, route_reason=r.reason, route=role)
        self._learn(text, final, background)
        return Reply(final, role, model, r.reason, called, streamed=streamed)

    # ------------------------------------------------------------------ research
    def _research(self, cid: int, text: str, r: Route, cb: Callbacks, background: bool) -> Reply:
        if r.role == "research" and text:
            topic, extra, depth = text[:400], "", 1
        else:  # follow-up of a research turn ("I want more")
            topic = self.memory.last_topic(cid) or text
            extra = (f"The user already got a first report and now asked: '{text}'. Go deeper: new sources, "
                     "more technical detail, and aspects the first report did not cover.")
            depth = 2
        if not topic:
            return Reply("Usage: /research <topic>", "research", "", "usage")
        if cb.on_event:
            cb.on_event(f"route: research · {self.cfg.model_for('reasoning')} · depth {depth} · {r.reason}")
        self.memory.add_message(cid, "user", text or topic, route="research", topic=topic)
        result = self.researcher.run(topic, extra=extra, depth=depth, emit=cb.on_event, on_token=cb.on_token)
        files = [str(result.path), *map(str, result.extra_files)]
        text_out = (f"**{result.title}**\n\n{result.summary}\n\n"
                    f"Report saved: {result.path}"
                    + (f"\nAlso: {', '.join(map(str, result.extra_files))}" if result.extra_files else "")
                    + f"\n\nSources read ({len(result.sources)}):\n\n"
                    + "\n".join(f"- [{s.n}] {s.title} — {s.url}" for s in result.sources[:12]))
        self.memory.add_message(cid, "assistant", text_out, model=self.cfg.model_for("reasoning"),
                                route_reason=r.reason, route="research", topic=topic)
        self._learn(text, result.summary, background)
        return Reply(text_out, "research", self.cfg.model_for("reasoning"), r.reason,
                     report_path=files[0], streamed=False)

    # ------------------------------------------------------------------ learning
    def _learn(self, user_text: str, assistant_text: str, background: bool) -> None:
        if not (self.cfg.memory.get("enabled", True) and self.cfg.memory.get("extract", True)):
            return
        if len(user_text.split()) < 3:   # "hi", "more" carry no durable facts
            return
        if background:
            self.facts.extract_async(user_text, assistant_text)
        else:
            self.facts.extract(user_text, assistant_text)
