# Configuration

The plugin is configured through the `agent_protocol` block in
`~/.config/hivemind-core/server.json`.

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

## Keys

| Key       | Type           | Required | Default | Description |
|-----------|----------------|----------|---------|-------------|
| `persona` | string or dict | yes      | none    | Path to a persona JSON file (tilde-expanded), or an inline persona config dict. |

### `persona` as a path

```json
{
  "hivemind-persona-agent-plugin": {
    "persona": "~/.config/ovos_persona/persona.json"
  }
}
```

The plugin loads the file at startup with `json.load`. Changes to the file after the
process starts are not hot-reloaded. Restart `hivemind-core` to pick up edits.

### `persona` as an inline dict

```json
{
  "hivemind-persona-agent-plugin": {
    "persona": {
      "name": "Inline Assistant",
      "solvers": ["ovos-chat-openai-plugin"],
      "ovos-chat-openai-plugin": {
        "api_url": "http://localhost:8000/v1",
        "model": "local-model",
        "key": "none"
      }
    }
  }
}
```

## Entry point

```
group: hivemind.agent.protocol
name:  hivemind-persona-agent-plugin
class: hivemind_persona_agent_plugin.PersonaAgentProtocol
```

The entry point is declared in `pyproject.toml`. `hivemind-core` loads it through
`AgentProtocolFactory.create("hivemind-persona-agent-plugin", config=...)`.

---
[← Query Flow](query_flow.md) · [Home](../README.md) · [Persona Format →](persona_format.md)
