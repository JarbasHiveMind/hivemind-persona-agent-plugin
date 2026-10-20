"""Offline solvers for a real ``Persona``, with no API key and no network."""
from typing import List, Optional

import pytest
from ovos_plugin_manager.templates.solvers import ChatMessageSolver


class CapitalsSolver(ChatMessageSolver):
    """Answers from the chat history, so a follow-up needs the earlier turn."""

    def continue_chat(self, messages: List, lang: Optional[str],
                      units: Optional[str] = None) -> Optional[str]:
        asked = messages[-1].content.lower()
        history = " ".join(m.content for m in messages[:-1]).lower()
        if "capital of france" in asked:
            return "Paris is the capital of France. It lies on the Seine."
        if "population" in asked and "paris" in history:
            return "Paris has about two million people."
        return None


class BrokenSolver(ChatMessageSolver):
    def continue_chat(self, messages, lang, units=None):
        raise RuntimeError("solver down")


def persona_config(solver_name: str) -> dict:
    return {"name": "TestPersona", "solvers": [solver_name],
            solver_name: {"enabled": True}}


@pytest.fixture
def solvers(monkeypatch):
    plugins = {"test-capitals-solver": CapitalsSolver,
               "test-broken-solver": BrokenSolver}
    monkeypatch.setattr("ovos_persona.solvers.get_utterance_handler_plugins",
                        lambda: plugins)
    return plugins
