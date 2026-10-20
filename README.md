# hivemind-persona-agent-plugin

An [ovos-persona](https://github.com/OpenVoiceOS/ovos-persona) agent protocol for
[HiveMind-core](https://github.com/JarbasHiveMind/HiveMind-core). The hub answers
natural-language utterances from an LLM or solver persona instead of a full OVOS skills
stack.

Unlike the default `hivemind-ovos-agent-plugin`, this agent needs no OVOS skills stack
and no messagebus service. It answers directly from the configured persona. It answers
three kinds of message:

- A `BUS` `recognizer_loop:utterance`, the message that `hivemind-client terminal` sends.
- A `BUS` `ovos.utterance.handle`, the message that a voice satellite sends.
- A `QUERY` or `CASCADE`.

The answer comes back sentence by sentence, so a satellite can start speaking before
generation finishes.

## Install

```bash
uv pip install --prerelease=allow hivemind-core hivemind-persona-agent-plugin
```

The plugin needs a hivemind-core alpha, so the install allows prereleases. A stable
`hivemind-core` resolves to 4.0.0, which conflicts with the plugin.

Or from source:

```bash
git clone https://github.com/JarbasHiveMind/hivemind-persona-agent-plugin
cd hivemind-persona-agent-plugin
uv pip install --prerelease=allow hivemind-core -e .
```

## Quickstart

### 1. Create a persona file

`ovos-persona` personas are JSON files. The `solvers` list holds plugin names. Each
plugin reads its settings from the key of the same name. Here is a minimal LLM-backed
persona:

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

### 4. Allow the utterance topics for the satellite

A satellite can send only the message types its credential allows. Allow both
utterance topics. A voice satellite sends `ovos.utterance.handle`, and
`hivemind-client terminal` sends `recognizer_loop:utterance`. If a topic is not
allowed, the hub replies with `hive.policy.denied` and code `acl_disallowed_type`.

```bash
hivemind-core add-client --name sat --access-key satkey --password "$(openssl rand -hex 16)" \
    --allow recognizer_loop:utterance --allow ovos.utterance.handle
```

The command prints the credentials. hivemind-core refuses a guessable password, so
use a generated one, and copy it to the satellite.

Satellites that connect to this hub receive answers from the persona as `speak`
messages, followed by `ovos.utterance.handled`.

## Configuration

All keys live under `"hivemind-persona-agent-plugin"` in `server.json`.

| Key       | Type           | Required | Description                                          |
|-----------|----------------|----------|------------------------------------------------------|
| `persona` | string or dict | yes      | Path to a persona JSON file, or an inline persona config. |

## How utterances are answered

A `BUS` utterance reaches the agent bus. The plugin builds the conversation from the
persona memory for the satellite's session, calls `Persona.stream`, and emits one
`speak` reply per sentence, then `ovos.utterance.handled`. hivemind-core does not
listen on the agent bus, so the plugin sends each reply to the peer named in its
`destination`. Utterances of one session are answered one at a time, in arrival order, and a follow-up
question sees the earlier turns of that session. A persona that fails or has no
answer gets a spoken error sentence. A blank utterance is not sent to the persona.

A `QUERY` or `CASCADE` calls `natural_language_query(utterance, lang)` on the agent.
The plugin yields each sentence as a chunk. A query carries no session, so the
persona answers each one on its own. If the persona fails or has no answer, the plugin
yields only the `None` sentinel. That is a decline: the hub escalates the query
upstream, and at the top of the chain the originator receives `hive.query.timeout` with
`error: "no_answer"`. After an answer, the sentinel makes the hub send
`hive.query.complete`.

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

## Credits

Developed by [TigreGótico](https://tigregotico.pt) for
[OpenVoiceOS](https://openvoiceos.org).

[![NGI0 Commons Fund](./ngi.png)](https://nlnet.nl/project/OpenVoiceOS)

This project was funded through the [NGI0 Commons Fund](https://nlnet.nl/commonsfund),
a fund established by [NLnet](https://nlnet.nl) with financial support from the
European Commission's [Next Generation Internet](https://ngi.eu) programme, under
the aegis of [DG Communications Networks, Content and Technology](https://commission.europa.eu/about-european-commission/departments-and-executive-agencies/communications-networks-content-and-technology_en)
under grant agreement No [101135429](https://cordis.europa.eu/project/id/101135429).
