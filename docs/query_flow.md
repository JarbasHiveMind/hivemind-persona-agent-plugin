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

1. **Satellite sends a QUERY HiveMessage.** The payload contains the utterance text and
   language tag.

2. **`hivemind-core` receives the message.** It runs the policy admission chain (ACL,
   blacklists, etc.) before proceeding.

3. **`hivemind-core` calls `natural_language_query(utterance, lang)`** on the
   `PersonaAgentProtocol` instance. This is the contract defined by
   `AgentProtocol` in `hivemind-plugin-manager`.

4. **The plugin calls `Persona.stream(messages, lang=lang)`** where `messages` is
   `[{"role": "user", "content": utterance}]`. The persona iterates its configured
   solver chain until one produces output.

5. **Each non-empty chunk yielded by `Persona.stream` is forwarded as a
   `QUERY.RESPONSE` HiveMessage** back to the originating satellite. Chunks are
   typically sentence-length, so the satellite can speak them in order as they arrive.

6. **After all chunks, the plugin yields `None`.** `hivemind-core` sends
   `hive.query.complete` to the satellite to signal that no further chunks follow.

## Error handling

If `Persona.stream` raises an exception, it is logged and the plugin immediately
yields `None`. The satellite receives `hive.query.complete` with no preceding answer
chunks. It can treat that as an empty/failed response.

## Streaming vs. full response

Because chunks are forwarded as they are produced, latency to first spoken word is
bounded by how quickly the first solver returns its first sentence — not by the total
generation time. This is the primary reason for the streaming contract in
`AgentProtocol`.
