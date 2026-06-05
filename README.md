# hivemind-persona-agent-plugin

An [ovos-persona](https://github.com/OpenVoiceOS/ovos-persona) agent protocol for
[HiveMind-core](https://github.com/JarbasHiveMind/HiveMind-core): the hub answers
natural-language queries from an LLM/solver persona instead of a full OVOS skills
stack.

It is the clean implementation of `AgentProtocol.natural_language_query` — the
persona *is* a question-answerer, so the seam maps directly onto
`Persona.stream`, yielding the answer sentence by sentence (and a final `None`
end-of-query sentinel) so a satellite can start speaking before generation
finishes.

## Configure

```json
{
  "agent_protocol": {
    "module": "hivemind-persona-agent-plugin",
    "hivemind-persona-agent-plugin": {
      "persona": "~/.config/ovos_persona/persona.json"
    }
  }
}
```

`persona` may be a path to a persona JSON file or an inline persona config dict.
