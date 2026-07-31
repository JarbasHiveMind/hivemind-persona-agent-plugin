# hivemind-persona-agent-plugin

An [ovos-persona](https://github.com/OpenVoiceOS/ovos-persona) agent protocol for
[HiveMind-core](https://github.com/JarbasHiveMind/HiveMind-core). The hub answers
natural-language queries from an LLM or solver persona instead of a full OVOS skills
stack.

Unlike the default `hivemind-ovos-agent-plugin`, this agent needs no OVOS bus and no
running skills. It answers queries directly from the configured persona. It streams
the model output sentence by sentence, so a satellite can start speaking before
generation finishes.

## Install

```bash
pip install hivemind-persona-agent-plugin
```

Or from source:

```bash
git clone https://github.com/JarbasHiveMind/hivemind-persona-agent-plugin
cd hivemind-persona-agent-plugin
pip install -e .
```

## Quickstart

### 1. Create a persona file

`ovos-persona` personas are JSON files. Here is a minimal LLM-backed persona:

```json
{
  "name": "MyAssistant",
  "solvers": [
    {
      "module": "ovos-solver-openai-plugin",
      "ovos-solver-openai-plugin": {
        "api_url": "http://localhost:8000/v1",
        "model": "local-model"
      }
    }
  ]
}
```

Save it to `~/.config/ovos_persona/persona.json`, or any path. You reference the path
in the config below.

### 2. Configure hivemind-core

Edit `~/.config/hivemind-core/server.json`:

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

The `persona` value can be either:
- a path to a persona JSON file (string, `~` expands), or
- an inline persona config dict.

### 3. Start hivemind-core

```bash
hivemind-core listen
```

Satellites that connect to this hub receive answers streamed from the persona.

## Configuration

All keys live under `"hivemind-persona-agent-plugin"` in `server.json`.

| Key       | Type           | Required | Description                                          |
|-----------|----------------|----------|------------------------------------------------------|
| `persona` | string or dict | yes      | Path to a persona JSON file, or an inline persona config. |

## How queries are answered

The QUERY handler in `hivemind-core` calls `natural_language_query(utterance, lang)`
on the active agent. This plugin implements that method. It calls
`Persona.stream(messages, lang=lang)` and yields each output chunk as the persona
produces it. The final `None` sentinel signals end of query to `hivemind-core`, which
sends a `hive.query.complete` control message back to the satellite.

See [`docs/query_flow.md`](docs/query_flow.md) for a detailed trace.

## Documentation

- [`docs/query_flow.md`](docs/query_flow.md): how a query travels from satellite to
  persona and back.
- [`docs/configuration.md`](docs/configuration.md): configuration reference.
- [`docs/persona_format.md`](docs/persona_format.md): how to write and configure an
  ovos-persona file.

## Related projects

- [ovos-persona](https://github.com/OpenVoiceOS/ovos-persona): the solver-chain
  persona engine this plugin calls.
- [HiveMind-core](https://github.com/JarbasHiveMind/HiveMind-core): the hub that
  loads this plugin.
- [hivemind-ovos-agent-plugin](https://github.com/JarbasHiveMind/hivemind-ovos-agent-plugin):
  the default agent protocol, backed by a full OVOS skills stack.

## License

Apache 2.0.
