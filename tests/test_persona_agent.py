"""The persona agent answers QUERY and a BUS utterance with a real Persona."""
import threading

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from ovos_bus_client.message import Message

from hivemind_persona_agent_plugin import PersonaAgentProtocol
from tests.conftest import persona_config

PEER = "sat::session-1"
SESSION = {"session_id": "ns:sat-session", "lang": "en-US"}


def _agent(solver="test-capitals-solver") -> PersonaAgentProtocol:
    return PersonaAgentProtocol(config={"persona": persona_config(solver)})


def _utterance(text: str) -> Message:
    """The message hivemind-core places on the agent bus for a BUS utterance."""
    return Message("recognizer_loop:utterance",
                   {"utterances": [text], "lang": "en-US"},
                   {"source": PEER, "peer": PEER, "destination": "skills",
                    "session": dict(SESSION)})


def _run(agent: PersonaAgentProtocol, message: Message, timeout: float = 5.0):
    """Emit *message* and return every message the bus saw, once handled."""
    seen = []
    done = threading.Event()
    agent.bus.on("message", lambda raw: seen.append(Message.deserialize(raw)))
    agent.bus.on("ovos.utterance.handled", lambda _: done.set())
    agent.bus.emit(message)
    assert done.wait(timeout), "ovos.utterance.handled never emitted"
    return seen


def _spoken(seen):
    return [m.data["utterance"] for m in seen if m.msg_type == "speak"]


def test_query_returns_the_persona_answer(solvers):
    chunks = list(_agent().natural_language_query("what is the capital of France",
                                                  "en-US"))
    assert chunks == ["Paris is the capital of France.",
                      "It lies on the Seine.", None]


def test_query_with_a_failing_solver_yields_only_the_sentinel(solvers):
    assert list(_agent("test-broken-solver").natural_language_query(
        "what is the capital of France", "en-US")) == [None]


def test_bus_utterance_is_answered_with_speak_and_handled(solvers):
    seen = _run(_agent(), _utterance("what is the capital of France"))

    replies = [m for m in seen if m.msg_type != "recognizer_loop:utterance"]
    assert [m.msg_type for m in replies] == ["speak", "speak",
                                             "ovos.utterance.handled"]
    assert _spoken(seen) == ["Paris is the capital of France.",
                             "It lies on the Seine."]
    assert all(m.context["destination"] == PEER for m in replies)


def test_follow_up_sees_the_earlier_turn(solvers):
    agent = _agent()
    _run(agent, _utterance("what is the capital of France"))
    seen = _run(agent, _utterance("and its population?"))
    assert _spoken(seen[-2:]) == ["Paris has about two million people."]


def test_follow_up_in_another_session_has_no_context(solvers):
    agent = _agent()
    _run(agent, _utterance("what is the capital of France"))
    other = _utterance("and its population?")
    other.context["session"] = {"session_id": "ns:other", "lang": "en-US"}
    seen = _run(agent, other)
    assert "Paris has about two million people." not in _spoken(seen)


def test_failing_solver_is_spoken_and_handled(solvers):
    seen = _run(_agent("test-broken-solver"),
                _utterance("what is the capital of France"))
    assert _spoken(seen) == ["The persona could not answer."]
    assert seen[-1].msg_type == "ovos.utterance.handled"


def test_replies_are_sent_to_the_connected_peer_only(solvers):
    agent = _agent()
    satellite, other = MagicMock(), MagicMock()
    agent.hm_protocol = SimpleNamespace(clients={PEER: satellite,
                                                 "other::s": other})

    _run(agent, _utterance("what is the capital of France"))

    sent = [c.args[0].payload for c in satellite.send.call_args_list]
    assert [m.msg_type for m in sent] == ["speak", "speak",
                                          "ovos.utterance.handled"]
    assert sent[0].data["utterance"] == "Paris is the capital of France."
    other.send.assert_not_called()


def test_the_request_is_not_sent_back_to_its_sender(solvers):
    agent = _agent()
    satellite = MagicMock()
    agent.hm_protocol = SimpleNamespace(clients={PEER: satellite})
    request = _utterance("what is the capital of France")
    request.context["destination"] = PEER

    _run(agent, request)

    assert all(c.args[0].payload.msg_type != "recognizer_loop:utterance"
               for c in satellite.send.call_args_list)


@pytest.mark.parametrize("session", [SESSION, {"session_id": "default"}, None],
                         ids=["named", "default", "none"])
@pytest.mark.parametrize("emit_legacy", ["true", "false"])
@pytest.mark.parametrize("topic", ["recognizer_loop:utterance",
                                   "ovos.utterance.handle"])
def test_each_utterance_topic_is_answered_exactly_once(
        solvers, monkeypatch, topic, emit_legacy, session):
    monkeypatch.setenv("OVOS_BUS_EMIT_LEGACY", emit_legacy)
    request = _utterance("what is the capital of France")
    request.msg_type = topic
    if session is None:
        del request.context["session"]
    else:
        request.context["session"] = dict(session)
    seen = _run(_agent(), request)
    threading.Event().wait(0.3)  # a second answer would arrive by now

    assert _spoken(seen) == ["Paris is the capital of France.",
                             "It lies on the Seine."]
    assert [m.msg_type for m in seen].count("ovos.utterance.handled") == 1


def test_blank_utterance_skips_the_persona_and_is_handled(solvers):
    agent = _agent()
    agent.persona = MagicMock()
    for utterances in ([""], ["  "], []):
        request = _utterance("x")
        request.data["utterances"] = utterances
        seen = _run(agent, request)
        assert [m.msg_type for m in seen if m.msg_type != request.msg_type] \
            == ["ovos.utterance.handled"]
    agent.persona.stream.assert_not_called()


def _session_utterance(text: str, session_id: str) -> Message:
    message = _utterance(text)
    message.context["session"] = {"session_id": session_id, "lang": "en-US"}
    return message


def test_same_session_utterances_are_answered_in_arrival_order(solvers):
    agent = _agent()
    order, gate = [], threading.Event()
    done = threading.Semaphore(0)

    def query(utterance, lang, session_id=None):
        if not order:
            gate.wait(5)
        order.append(utterance)
        yield "ok"
        yield None

    agent.natural_language_query = query
    agent.bus.on("ovos.utterance.handled", lambda _: done.release())
    for i in range(6):
        agent.bus.emit(_session_utterance(f"u{i}", "s"))
    gate.set()
    for _ in range(6):
        assert done.acquire(timeout=10)
    assert order == [f"u{i}" for i in range(6)]


def test_a_queued_session_does_not_hold_workers_from_other_sessions(solvers):
    agent = _agent()
    gate = threading.Event()

    def query(utterance, lang, session_id=None):
        if session_id == "busy":
            gate.wait(10)
        yield "ok"
        yield None

    agent.natural_language_query = query
    victim_done = threading.Event()
    agent.bus.on("ovos.utterance.handled", lambda m: victim_done.set()
                 if m.context["session"]["session_id"] == "victim" else None)
    for i in range(40):
        agent.bus.emit(_session_utterance(f"slow{i}", "busy"))
    agent.bus.emit(_session_utterance("hello", "victim"))

    answered = victim_done.wait(5)
    gate.set()
    assert answered, "another session's answer waited behind the queued session"


def test_worker_threads_are_daemons(solvers):
    agent = _agent()
    _run(agent, _utterance("what is the capital of France"))
    workers = [t for t in threading.enumerate()
               if t.name.startswith("persona-answer")]
    assert workers
    assert all(t.daemon for t in workers)


def test_reply_for_a_disconnected_peer_logs_a_warning(solvers, monkeypatch):
    warned = []
    monkeypatch.setattr("hivemind_persona_agent_plugin.LOG.warning",
                        lambda text, *a, **k: warned.append(text))
    agent = _agent()
    clients = {PEER: MagicMock()}
    agent.hm_protocol = SimpleNamespace(clients=clients)
    real = agent.natural_language_query

    def peer_leaves_mid_answer(utterance, lang, session_id=None):
        del clients[PEER]
        yield from real(utterance, lang, session_id)

    agent.natural_language_query = peer_leaves_mid_answer

    _run(agent, _utterance("what is the capital of France"))

    assert any(PEER in w and "ns:sat-session" in w and w.startswith("speak")
               for w in warned), warned
    assert not any(w.startswith("recognizer_loop:utterance") for w in warned)


def test_readme_quickstart_persona_loads():
    """The persona in the README quickstart builds a real Persona."""
    import json
    import re
    from pathlib import Path

    readme = (Path(__file__).parent.parent / "README.md").read_text()
    blocks = re.findall(r"```json\n(.*?)\n```", readme, re.S)
    persona = next(json.loads(b) for b in blocks if '"solvers"' in b
                   and '"persona"' not in b)
    agent = PersonaAgentProtocol(config={"persona": persona})
    assert agent.persona.name == "MyAssistant"
    assert list(agent.persona.solvers.loaded_modules) == [
        "ovos-chat-openai-plugin"]


def test_a_failed_thread_start_does_not_strand_the_session(solvers, monkeypatch):
    agent = _agent()
    real_start = threading.Thread.start
    calls = []

    def start_once_fails(self):
        calls.append(self.name)
        if len(calls) == 1:
            raise RuntimeError("can't start new thread")
        real_start(self)

    monkeypatch.setattr(threading.Thread, "start", start_once_fails)
    agent.bus.emit(_utterance("what is the capital of France"))

    seen = _run(agent, _utterance("what is the capital of France"))
    assert _spoken(seen) == ["Paris is the capital of France.",
                             "It lies on the Seine."]


def test_a_failed_thread_start_tells_the_peer(solvers, monkeypatch):
    agent = _agent()

    def start_fails(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Thread, "start", start_fails)
    seen = _run(agent, _utterance("what is the capital of France"))

    replies = [m for m in seen if m.msg_type != "recognizer_loop:utterance"]
    assert [m.msg_type for m in replies] == ["speak", "ovos.utterance.handled"]
    assert _spoken(seen) == [
        "Error contacting persona: can't start new thread"]
    assert all(m.context["destination"] == PEER for m in replies)
    assert agent._pending == {}
    assert agent._workers == 0
    assert agent._work.qsize() == 0


def test_queued_utterances_of_a_departed_peer_do_not_call_the_persona(
        solvers, monkeypatch):
    agent = _agent()
    clients = {PEER: MagicMock()}
    agent.hm_protocol = SimpleNamespace(clients=clients)
    warned, calls = [], []
    monkeypatch.setattr("hivemind_persona_agent_plugin.LOG.warning",
                        lambda text, *a, **k: warned.append(text))
    started, gate = threading.Event(), threading.Event()

    def query(utterance, lang, session_id=None):
        calls.append(utterance)
        started.set()
        gate.wait(5)
        yield "ok"
        yield None

    agent.natural_language_query = query
    done = threading.Semaphore(0)
    agent.bus.on("ovos.utterance.handled", lambda _: done.release())
    agent.bus.emit(_session_utterance("one", "s"))
    assert started.wait(5)
    agent.bus.emit(_session_utterance("two", "s"))
    agent.bus.emit(_session_utterance("three", "s"))
    del clients[PEER]
    gate.set()
    assert done.acquire(timeout=5)
    threading.Event().wait(0.3)

    assert calls == ["one"]
    assert sum("is gone; utterance dropped" in w for w in warned) == 2
