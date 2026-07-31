# Persona Format

A persona is a JSON configuration that tells `ovos-persona` which solvers to use, and
in what order, when it answers a query. Full documentation for the persona format
lives in [ovos-persona](https://github.com/OpenVoiceOS/ovos-persona). This page
covers the fields relevant to HiveMind use.

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

Any `QuestionSolver` plugin compatible with `ovos-plugin-manager` works. Common
choices:

- `ovos-solver-openai-plugin`: an OpenAI-compatible REST endpoint, local or remote.
- `ovos-solver-persona-plugin`: persona chaining, where one persona delegates to
  another.
- `neon-solver-*` packages are excluded. They pin old OVOS versions and break
  dependencies.

The plugin tries solvers in list order. The first solver that returns a non-empty
answer wins. The plugin does not call the remaining solvers.

## Storing the persona file

The conventional location is `~/.config/ovos_persona/<name>.json`. Any path readable
by the `hivemind-core` process works. Reference it in `server.json` as an absolute
path, or with a leading `~`.

---
[← Configuration](configuration.md) · [Home](../README.md)
