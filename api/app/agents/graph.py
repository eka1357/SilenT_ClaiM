"""LangGraph StateGraph wiring and thread resume runner for Silent Claim."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents.nodes import (
    AgentRuntime,
    _route_after_ask,
    _route_after_classify,
    _route_after_confirm,
    build_nodes,
)
from app.agents.state import ClaimState
from app.models import Ask, now_ist


def build_claim_graph(
    runtime: AgentRuntime,
    *,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Compile the Silent Claim LangGraph workflow with an in-memory checkpointer."""
    nodes = build_nodes(runtime)
    builder = StateGraph(ClaimState)
    builder.add_node("sense", nodes["sense"])
    builder.add_node("confirm", nodes["confirm"])
    builder.add_node("ask", nodes["ask"])
    builder.add_node("classify", nodes["classify"])
    builder.add_node("file", nodes["file"])
    builder.add_node("close", nodes["close"])
    builder.add_node("human_review", nodes["human_review"])

    builder.add_edge(START, "sense")
    builder.add_edge("sense", "confirm")
    builder.add_conditional_edges(
        "confirm",
        _route_after_confirm,
        {"ask": "ask", "end": END},
    )
    builder.add_conditional_edges(
        "ask",
        _route_after_ask,
        {"file": "file", "classify": "classify"},
    )
    builder.add_conditional_edges(
        "classify",
        _route_after_classify,
        {"file": "file", "close": "close", "human_review": "human_review"},
    )
    builder.add_edge("file", END)
    builder.add_edge("close", END)
    builder.add_edge("human_review", END)

    saver = checkpointer if checkpointer is not None else InMemorySaver()
    return builder.compile(checkpointer=saver)


class ClaimGraphRunner:
    """Thread-safe manager owning the compiled LangGraph workflow and InMemorySaver."""

    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime
        self._lock = threading.Lock()
        self._checkpointer: InMemorySaver = InMemorySaver()
        self._graph = build_claim_graph(runtime, checkpointer=self._checkpointer)

    def reset(self) -> None:
        """Replace checkpointer and clear cached run state across scenario resets."""
        with self._lock:
            self.runtime.clear_run_caches()
            self._checkpointer = InMemorySaver()
            self._graph = build_claim_graph(self.runtime, checkpointer=self._checkpointer)

    def run_shop_day(
        self,
        *,
        shop_id: str,
        day_iso: str,
        street_id: str = "panagal_park_road",
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Run sense -> confirm -> (ask interrupt | END) for a single shop on `day_iso`."""
        tid = thread_id or f"shop_run_{day_iso.replace('-', '')}_{shop_id}"
        config = {"configurable": {"thread_id": tid}}
        initial = ClaimState(shop_id=shop_id, day=day_iso, street_id=street_id)
        with self._lock:
            result = self._graph.invoke(initial, config=config)

        # Keep Ask.thread_id synchronized with the exact LangGraph thread that paused on it.
        if result.get("__interrupt__"):
            intr = result["__interrupt__"][0]
            payload = intr.value if hasattr(intr, "value") else {}
            ask_id = payload.get("ask_id") if isinstance(payload, dict) else None
            if ask_id:
                with self.runtime.db.session() as sess:
                    ask_row = sess.get(Ask, ask_id)
                    if ask_row is not None and ask_row.thread_id != tid:
                        ask_row.thread_id = tid
        return result

    def resume_consent(
        self,
        ask: Ask,
        *,
        answered_at: datetime | None = None,
        simulated_label: str | None = None,
    ) -> dict[str, Any]:
        """Resume a paused consent Ask thread and transition to `file`."""
        ts = answered_at or now_ist()
        config = {"configurable": {"thread_id": ask.thread_id}}
        resume_payload = {
            "reply_type": "tap",
            "answered_at": ts.isoformat(),
            "simulated_label": simulated_label,
        }
        with self._lock:
            return self._graph.invoke(Command(resume=resume_payload), config=config)

    def resume_voice(
        self,
        ask: Ask,
        *,
        audio_bytes: bytes,
        filename: str = "reply.wav",
        content_type: str = "audio/wav",
        answered_at: datetime | None = None,
        simulated_label: str | None = None,
    ) -> dict[str, Any]:
        """Resume a paused voice Ask thread -> classify() -> file/close/human_review."""
        ts = answered_at or now_ist()
        config = {"configurable": {"thread_id": ask.thread_id}}
        self.runtime.put_voice_blob(ask.id, audio_bytes, filename, content_type)
        resume_payload = {
            "reply_type": "voice",
            "ask_id": ask.id,
            "answered_at": ts.isoformat(),
            "simulated_label": simulated_label,
        }
        try:
            with self._lock:
                return self._graph.invoke(Command(resume=resume_payload), config=config)
        finally:
            self.runtime.pop_voice_blob(ask.id)
