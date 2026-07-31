# Query Flow

This document traces how a natural-language query travels from a HiveMind satellite
through `hivemind-core` to the persona, and how the streamed answer returns to the
satellite.

## Overview

```
satellite                hivemind-core                 PersonaAgentProtocol
    |                         |                                  |
    |---HiveMessage(QUERY)--->|                                  |
    |                         | policy check                     |
    |                         |---natural_language_query(utt, lang)->|
    |                         |                                  | Persona.stream(...)
    |                         |<--yield "sentence 1"-------------|
    |<--HiveMessage(QUERY.RESPONSE, chunk="sentence 1")----------|
    |                         |<--yield "sentence 2"-------------|
    |<--HiveMessage(QUERY.RESPONSE, chunk="sentence 2")----------|
    |                         |<--yield None (sentinel)----------|
    |<--HiveMessage(hive.query.complete)-------------------------|
```

## Step by step

1. **Satellite sends a QUERY HiveMessage.** The payload holds the utterance text and
   the language tag.

2. **`hivemind-core` receives the message.** It runs the policy admission chain (ACL,
   blacklists, and so on) before it proceeds.

3. **`hivemind-core` calls `natural_language_query(utterance, lang)`** on the
   `PersonaAgentProtocol` instance. This is the contract that `AgentProtocol` defines
   in `hivemind-plugin-manager`.

4. **The plugin calls `Persona.stream(messages, lang=lang)`**, where `messages` is
   `[{"role": "user", "content": utterance}]`. The persona works through its
   configured solver chain until one solver produces output.

5. **The plugin forwards each non-empty chunk that `Persona.stream` yields** as a
   `QUERY.RESPONSE` HiveMessage back to the originating satellite. Chunks are
   typically sentence-length, so the satellite can speak them in order as they
   arrive.

6. **After the last chunk, the plugin yields `None`.** `hivemind-core` then sends
   `hive.query.complete` to the satellite, to signal that no more chunks follow.

## Error handling

If `Persona.stream` raises an exception, the plugin logs it and yields `None`
immediately. The satellite receives `hive.query.complete` with no answer chunks
before it. The satellite can treat that as an empty or failed response.

## Streaming vs. full response

Because the plugin forwards chunks as they are produced, the latency to the first
spoken word depends on how quickly the first solver returns its first sentence, not
on the total generation time. This is the main reason for the streaming contract in
`AgentProtocol`.

---
[Home](../README.md) · [Configuration →](configuration.md)
