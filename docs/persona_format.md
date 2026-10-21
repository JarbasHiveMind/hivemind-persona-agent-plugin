# Persona Format

A persona is a JSON configuration that tells `ovos-persona` which solvers to use, and
in what order, when it answers a query. Full documentation for the persona format
lives in [ovos-persona](https://github.com/OpenVoiceOS/ovos-persona). This page
covers the fields relevant to HiveMind use.

## Minimal example

```json
{
  "name": "MyAssistant",
  "solvers": ["ovos-chat-openai-plugin"],
  "ovos-chat-openai-plugin": {
    "api_url": "http://localhost:8000/v1",
    "model": "local-model",
    "key": "none"
  }
}
```

## Fields

| Field     | Type   | Description |
|-----------|--------|-------------|
| `name`    | string | Human-readable name for the persona. Used in logs. Defaults to `"HiveMind Persona"` if absent. |
| `solvers` | list   | Ordered list of plugin names, as strings. The persona tries them in this order. |
| `<plugin name>` | object | The settings of the plugin with that name, as a sibling key of `solvers`. |

## Solver plugins

Any solver or chat engine plugin that `ovos-plugin-manager` can load works. A common
choice is `ovos-chat-openai-plugin` from `ovos-openai-plugin`: an OpenAI-compatible
REST endpoint, local or remote. `neon-solver-*` packages are excluded. They pin old
OVOS versions and break dependencies.

The persona tries plugins in list order. The first plugin that returns a non-empty
answer wins. The persona does not call the remaining plugins.

## Storing the persona file

The conventional location is `~/.config/ovos_persona/<name>.json`. Any path readable
by the `hivemind-core` process works. Reference it in `server.json` as an absolute
path, or with a leading `~`.

---
[← Configuration](configuration.md) · [Home](../README.md)
