# Query Flow

This document traces how an utterance travels from a HiveMind satellite through
`hivemind-core` to the persona, and how the answer returns to the satellite. There are
two paths. A `BUS` utterance is what `hivemind-client terminal` and a voice satellite
send. A `QUERY` or `CASCADE` is what a node sends to ask its upstream.

## BUS utterance

```
satellite              hivemind-core               PersonaAgentProtocol
    |                       |                               |
    |--BUS utterance------->| policy check                  |
    |                       |--agent bus: utterance-------->|
    |                       |                               | Persona.stream(...)
    |                       |<--speak, destination=peer-----|
    |<--BUS speak-----------| (relayed by the plugin)       |
    |<--BUS speak-----------|                               |
    |<--BUS ovos.utterance.handled--------------------------|
```

1. **The satellite sends a `BUS` message** of type `recognizer_loop:utterance` or
   `ovos.utterance.handle`. The satellite credential must allow that type.

2. **`hivemind-core` admits the message.** It runs the policy chain, stamps the
   satellite's peer id in `source`, sets the Layer-1 session id, and places the message
   on the agent bus.

3. **The plugin answers it.** The plugin listens on both utterance topics, and answers
   each utterance once even when the bus also delivers it under the other topic name.
   One exception exists: ovos-utils 0.12.0a1 to 0.15.5a1 answer an utterance of the
   session `default` twice, because their FakeBus delivers the bridged copy as a second
   utterance. ovos-utils 0.8.x and 0.15.6a1 or later do not. A blank utterance gets only
   `ovos.utterance.handled`. Otherwise the plugin builds the conversation from the
   persona memory for that session id and calls `Persona.stream(messages, session)`.
   It emits one `speak` reply per sentence, then `ovos.utterance.handled`. Utterances
   of one session are answered in arrival order, so a follow-up sees the earlier
   turns. An utterance that waits for its session holds no worker thread.

4. **The plugin relays the replies.** `hivemind-core` does not listen on the agent bus.
   `Message.reply` puts the peer id in `destination`, and the plugin sends each reply
   to that connected peer. A reply for a peer that is no longer connected is logged at
   WARNING with the destination and the session.

5. **On failure the satellite hears an error sentence.** If the persona raises, or no
   solver produces an answer, the plugin speaks one sentence that says so, then emits
   `ovos.utterance.handled`.

## QUERY and CASCADE

```
satellite                hivemind-core                 PersonaAgentProtocol
    |                         |                                  |
    |---HiveMessage(QUERY)--->|                                  |
    |                         | policy check                     |
    |                         |---natural_language_query(utt, lang)->|
    |                         |                                  | Persona.stream(...)
    |                         |<--yield "sentence 1"-------------|
    |<--QUERY answer chunk, is_response=true---------------------|
    |                         |<--yield "sentence 2"-------------|
    |<--QUERY answer chunk, is_response=true---------------------|
    |                         |<--yield None (sentinel)----------|
    |<--hive.query.complete-----------------------------------|
```

1. **The satellite sends a `QUERY`** that wraps a `recognizer_loop:utterance`.

2. **`hivemind-core` runs the policy chain** and calls
   `natural_language_query(utterance, lang)` on the plugin. This is the contract that
   `AgentProtocol` defines in `hivemind-plugin-manager`.

3. **The plugin calls `Persona.stream`** with the user message and a session that
   carries `lang`. A query has no session id of its own, so the persona answers it
   without history.

4. **The plugin yields each non-empty chunk.** `hivemind-core` sends each chunk to the
   originator as a `QUERY` message with `is_response` set (HIVEMIND-MSG-1 section 5.2).

5. **After the last chunk, the plugin yields `None`.** `hivemind-core` then sends
   `hive.query.complete`.

## Error handling

If `Persona.stream` raises, or the persona has no answer, the plugin logs it and yields
`None` as its first item. That is a decline (HIVEMIND-AGENT-1 section 3.0). The hub
escalates the query upstream. At the top of the chain the originator receives
`hive.query.timeout` with `error: "no_answer"`, not `hive.query.complete`.

## Streaming vs. full response

The plugin forwards chunks as the persona produces them. The latency to the first
spoken word depends on how quickly the first solver returns its first sentence, not
on the total generation time.

---
[Home](../README.md) · [Configuration →](configuration.md)
