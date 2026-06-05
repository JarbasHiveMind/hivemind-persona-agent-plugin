"""hivescope e2e: a satellite QUERY is answered by the persona agent and
streamed back. The LLM/solver is mocked deterministically (no API keys / no
solver in CI), so this exercises the PersonaAgentProtocol.natural_language_query
streaming contract through a real hivemind-core QUERY round-trip."""
from unittest import mock

import pytest

pytest.importorskip("hivescope")

from hivemind_bus_client.message import HiveMessage, HiveMessageType  # noqa: E402
from ovos_bus_client.message import Message  # noqa: E402
from hivescope.topology import TopologyBuilder  # noqa: E402


def _query(utt, qid, peer):
    inner = HiveMessage(HiveMessageType.BUS,
                        payload=Message("recognizer_loop:utterance", {"utterances": [utt]}))
    return HiveMessage(HiveMessageType.QUERY, payload=inner,
                       metadata={"query_id": qid, "originator_peer": peer})


def test_persona_answers_query_streaming():
    with mock.patch("hivemind_persona_agent_plugin.Persona") as MockPersona:
        # the persona streams two sentences then ends
        MockPersona.return_value.stream.side_effect = \
            lambda *a, **k: iter(["Paris is the capital ", "of France."])
        from hivemind_persona_agent_plugin import PersonaAgentProtocol
        agent = PersonaAgentProtocol(config={"persona": {"name": "test"}})

        b = TopologyBuilder()
        m = b.add_master("M0", agent_protocol=agent)
        m.register_satellite("k", password="p",
                             allowed_types=["recognizer_loop:utterance"])
        b.add_satellite("S0", upstream=m,
                        allowed_types=["recognizer_loop:utterance"])
        b.start_all()
        try:
            s = b.get_satellite("S0")
            s.send(_query("capital of France", "q1", s.peer))
            recv = s.recorder.wait_for(HiveMessageType.QUERY.value,
                                       direction="in", timeout=4.0)
            assert recv is not None, "persona QUERY answer never reached the satellite"
            # the streamed answer arrived as >=2 QUERY response chunks
            chunks = s.recorder.received(HiveMessageType.QUERY.value, direction="in")
            assert len(chunks) >= 2
        finally:
            b.stop_all()
