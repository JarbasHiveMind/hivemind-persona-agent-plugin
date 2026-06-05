"""HiveMind agent protocol backed by an ovos-persona LLM/solver.

Answers natural-language queries directly from the persona — no OVOS bus
round-trip — streaming the model's output as it is produced. This is the
clean case for ``AgentProtocol.natural_language_query``: the agent *is* a
question-answerer, so the abstraction maps straight onto ``Persona.stream``.
"""
import dataclasses
import json
import os
from typing import Any, Dict, Iterator, Optional

from ovos_persona import Persona
from ovos_utils.log import LOG

from hivemind_plugin_manager.protocols import AgentProtocol

from hivemind_persona_agent_plugin.version import __version__


@dataclasses.dataclass
class PersonaAgentProtocol(AgentProtocol):
    """AgentProtocol that answers queries from an ovos-persona."""
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        cfg = self.config.get("persona", {})
        if isinstance(cfg, str):  # a path to a persona.json
            with open(os.path.expanduser(cfg)) as f:
                cfg = json.load(f)
        self.persona = Persona(name=cfg.get("name", "HiveMind Persona"),
                               config=cfg)

    def natural_language_query(self, utterance: str,
                               lang: str) -> "Iterator[Optional[str]]":
        """Stream the persona's answer sentence by sentence, then yield the
        ``None`` end-of-query sentinel."""
        messages = [{"role": "user", "content": utterance}]
        try:
            for chunk in self.persona.stream(messages, lang=lang):
                if chunk:
                    yield chunk
        except Exception:
            LOG.exception("persona natural_language_query failed")
        yield None
