# Persona Format

A persona is a JSON configuration that tells `ovos-persona` which solvers to use (and
in what order) when answering a query. Full documentation for the persona format lives
in [ovos-persona](https://github.com/OpenVoiceOS/ovos-persona); this page covers the
key fields relevant to HiveMind use.

## Minimal example

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

## Fields

| Field     | Type   | Description |
|-----------|--------|-------------|
| `name`    | string | Human-readable name for the persona. Used in logs. Defaults to `"HiveMind Persona"` if absent. |
| `solvers` | list   | Ordered list of solver plugin configs. Each entry has a `"module"` key naming the solver plugin, plus a same-named key for its config. |

## Solver plugins

Any `QuestionSolver` plugin compatible with `ovos-plugin-manager` can be used. Common
choices:

- **`ovos-solver-openai-plugin`** — OpenAI-compatible REST endpoint (local or remote).
- **`ovos-solver-persona-plugin`** — persona chaining (one persona delegates to
  another).
- **`neon-solver-*` packages are explicitly excluded** — they pin ancient OVOS
  versions and break dependencies.

Solvers are tried in list order. The first solver that returns a non-empty answer wins;
remaining solvers are not called.

## Storing the persona file

The conventional location is `~/.config/ovos_persona/<name>.json`. Any path readable
by the `hivemind-core` process works. Reference it in `server.json` either as an
absolute path or with a leading `~`.
