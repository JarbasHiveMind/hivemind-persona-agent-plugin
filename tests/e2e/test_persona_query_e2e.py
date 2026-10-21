"""hivescope e2e: a satellite QUERY and a BUS utterance are answered by the
persona agent. The persona is a real ``Persona`` with an offline solver (see
``tests/conftest.py``), so the answer text comes through the real
``Persona.stream`` call and a real hivemind-core round-trip."""
import time

import pytest

from hivemind_bus_client.message import HiveMessage, HiveMessageType  # noqa: E402
from ovos_bus_client.message import Message  # noqa: E402
from hivescope.topology import TopologyBuilder  # noqa: E402


ALLOWED = ["recognizer_loop:utterance", "ovos.utterance.handle"]


def _query(utt, qid, peer):
    inner = HiveMessage(HiveMessageType.BUS,
                        payload=Message("recognizer_loop:utterance", {"utterances": [utt]}))
    return HiveMessage(HiveMessageType.QUERY, payload=inner,
                       metadata={"query_id": qid, "originator_peer": peer})


def _speak_texts(records):
    """Unwrap recorded QUERY response chunks (HiveMessage(QUERY,
    payload=HiveMessage(BUS, payload=Message("speak")))) to the spoken text."""
    texts = []
    for rec in records:
        payload = rec.payload
        for _ in range(4):
            if isinstance(payload, Message):
                if payload.msg_type == "speak":
                    texts.append(payload.data.get("utterance", ""))
                break
            if isinstance(payload, dict):
                if payload.get("type") == "speak":
                    texts.append(payload.get("data", {}).get("utterance", ""))
                    break
                payload = payload.get("payload")
            else:
                payload = getattr(payload, "payload", None)
            if payload is None:
                break
    return texts


def _hub(solvers, satellites=("S0",)):
    from hivemind_persona_agent_plugin import PersonaAgentProtocol
    from tests.conftest import persona_config
    agent = PersonaAgentProtocol(
        config={"persona": persona_config("test-capitals-solver")})
    b = TopologyBuilder()
    m = b.add_master("M0", agent_protocol=agent)
    m.register_satellite("k", password="p", allowed_types=ALLOWED)
    for name in satellites:
        b.add_satellite(name, upstream=m, allowed_types=ALLOWED)
    b.start_all()
    return b


def _bus_messages(sat, msg_type):
    """Data of every BUS message of *msg_type* the satellite received."""
    return [r.payload["data"] for r in sat.recorder.received(
        HiveMessageType.BUS.value, direction="in")
        if isinstance(r.payload, dict) and r.payload.get("type") == msg_type]


def _wait_handled(sat, timeout=6.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _bus_messages(sat, "ovos.utterance.handled"):
            return
        time.sleep(0.1)
    raise AssertionError("ovos.utterance.handled never reached the satellite")


def test_persona_answers_query_streaming(solvers):
    b = _hub(solvers)
    try:
        s = b.get_satellite("S0")
        s.send(_query("what is the capital of France", "q1", s.peer))
        deadline = time.time() + 4.0
        while time.time() < deadline:
            spoken = _speak_texts(s.recorder.received(
                HiveMessageType.QUERY.value, direction="in"))
            if len(spoken) >= 2:
                break
            time.sleep(0.05)
        assert spoken == ["Paris is the capital of France.",
                          "It lies on the Seine."]
    finally:
        b.stop_all()


@pytest.mark.parametrize("topic", ["recognizer_loop:utterance",
                                   "ovos.utterance.handle"])
def test_persona_answers_bus_utterance_to_its_peer_only(solvers, topic):
    b = _hub(solvers, satellites=("S0", "S1"))
    try:
        s0, s1 = b.get_satellite("S0"), b.get_satellite("S1")
        s0.send(HiveMessage(HiveMessageType.BUS, payload=Message(
            topic, {"utterances": ["what is the capital of France"],
                    "lang": "en-US"})))
        _wait_handled(s0)
        assert [d["utterance"] for d in _bus_messages(s0, "speak")] == ["Paris is the capital of France.",
                                           "It lies on the Seine."]
        assert _bus_messages(s1, "speak") == []
        assert _bus_messages(s1, "ovos.utterance.handled") == []
    finally:
        b.stop_all()
