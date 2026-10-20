"""HiveMind agent protocol backed by an ovos-persona LLM/solver.

Answers natural-language queries directly from the persona, with no OVOS skills
stack, streaming the model's output as it is produced. Two kinds of message
reach the persona:

* ``QUERY`` and ``CASCADE`` arrive through ``natural_language_query``.
* A ``BUS`` utterance arrives on the agent bus (HIVEMIND-AGENT-1 section 3):
  ``recognizer_loop:utterance`` from ``hivemind-client terminal`` or
  ``ovos.utterance.handle`` from a voice satellite. The plugin listens on both
  topics. Each utterance is answered once, even when the bus also delivers it
  under the other name. The one exception is a ``default`` session id on
  ovos-utils 0.12.0a1 to 0.15.5a1: those FakeBus releases deliver the bridged
  copy as a second utterance, and the plugin answers both. ovos-utils 0.8.x
  and 0.15.6a1 and later do not. The plugin answers with ``speak`` replies and
  ``ovos.utterance.handled``, and relays them to the peer the reply names.
"""
import dataclasses
import json
import os
import queue
import threading
from collections import deque
from typing import Any, Dict, Iterator, Optional

from hivemind_bus_client.message import HiveMessage, HiveMessageType
from hivemind_plugin_manager.protocols import AgentProtocol
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_persona import Persona
from ovos_plugin_manager.templates.agents import AgentMessage, MessageRole
from ovos_utils.log import LOG

from hivemind_persona_agent_plugin.version import __version__


#: Most utterances answered at once, across all sessions.
MAX_WORKERS = 16


@dataclasses.dataclass
class PersonaAgentProtocol(AgentProtocol):
    """AgentProtocol that answers queries from an ovos-persona.

    A ``BUS`` utterance carries the peer's Layer-1 session id. The persona
    keeps the conversation history under that id, so a follow-up question sees
    the earlier turns. A ``QUERY`` has no session id and is answered on its own.
    Utterances of one session are answered one at a time, in arrival order;
    a waiting utterance holds no worker. Different sessions are answered in parallel.
    """
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        cfg = self.config.get("persona", {})
        if isinstance(cfg, str):  # a path to a persona.json
            with open(os.path.expanduser(cfg)) as f:
                cfg = json.load(f)
        self.persona = Persona(name=cfg.get("name", "HiveMind Persona"),
                               config=cfg)
        self._work: "queue.SimpleQueue" = queue.SimpleQueue()
        # session id -> utterances that wait for the running answer of that
        # session. A session is a key only while one of its answers runs.
        self._pending: Dict[str, deque] = {}
        self._pending_guard = threading.Lock()
        self._workers = 0
        self._idle = 0
        self.bus.on("recognizer_loop:utterance", self.handle_utterance)
        self.bus.on("ovos.utterance.handle", self.handle_utterance)
        self.bus.on("message", self.handle_internal_message)

    def natural_language_query(self, utterance: str, lang: str,
                               session_id: Optional[str] = None
                               ) -> "Iterator[Optional[str]]":
        """Stream the persona's answer sentence by sentence, then yield the
        ``None`` end-of-query sentinel.

        With a ``session_id`` the exchange is stored as conversation history
        under that id. Without one the persona answers a single question.
        Yields only ``None`` when the persona has no answer or raises.
        """
        sess = Session(session_id=session_id, lang=lang)
        answer = []
        try:
            messages = self.persona.get_messages(utterance, sess)
            for chunk in self.persona.stream(messages, sess):
                if chunk:
                    answer.append(chunk)
                    yield chunk
        except Exception:
            LOG.exception("persona natural_language_query failed")
        if session_id and answer and self.persona.memory is not None:
            self.persona.memory.update_history(
                [AgentMessage(MessageRole.USER, utterance)], session_id)
            self.persona.memory.update_history(
                [AgentMessage(MessageRole.ASSISTANT, " ".join(answer))],
                session_id)
        yield None

    # ------------------------------------------------------------------
    # Layer-1 bus mode (HIVEMIND-AGENT-1 section 3)
    # ------------------------------------------------------------------

    def handle_utterance(self, message: Message) -> None:
        """Answer an utterance from the agent bus.

        The persona can take as long as its model needs, so the answer runs on
        a daemon worker thread and does not hold up the connection that
        delivered the message. A blank utterance is not sent to the persona.
        """
        utterances = message.data.get("utterances") or []
        if not utterances or not str(utterances[0]).strip():
            self.bus.emit(message.reply("ovos.utterance.handled", {}))
            return
        session = message.context.get("session") or {}
        lang = (message.data.get("lang") or message.context.get("lang")
                or session.get("lang") or "en-US")
        session_id = session.get("session_id")
        job = (message, str(utterances[0]), lang, session_id)
        start_error = None
        with self._pending_guard:
            if session_id in self._pending:
                self._pending[session_id].append(job)
                return
            if self._work.qsize() >= self._idle and self._workers < MAX_WORKERS:
                try:
                    threading.Thread(
                        target=self._worker, daemon=True,
                        name=f"persona-answer-{self._workers + 1}").start()
                except RuntimeError as exc:
                    start_error = exc
                else:
                    self._workers += 1
            if start_error is None:
                if session_id:
                    self._pending[session_id] = deque()
                self._work.put(job)
        if start_error is not None:
            LOG.error(f"could not start a persona worker thread: {start_error}")
            self.bus.emit(message.reply(
                "speak", {"utterance": f"Error contacting persona: {start_error}",
                          "lang": lang}))
            self.bus.emit(message.reply("ovos.utterance.handled", {}))

    def _worker(self) -> None:
        while True:
            with self._pending_guard:
                self._idle += 1
            job = self._work.get()
            with self._pending_guard:
                self._idle -= 1
            self._drain(job)

    def _drain(self, job) -> None:
        """Answer *job*, then the utterances that queued behind it in its session.

        One session holds one worker at a time and its answers run in arrival
        order. An utterance that waits for its session holds no worker. A
        queued utterance whose peer has left is dropped without calling the
        persona.
        """
        while job:
            peer = job[0].context.get("source")
            if self.hm_protocol and peer not in self.clients:
                LOG.warning(f"peer {peer} is gone; utterance dropped "
                            f"(session {job[3]})")
            else:
                try:
                    self._answer_utterance(*job)
                except Exception:
                    LOG.exception("could not finish an utterance")
            session_id = job[3]
            if not session_id:
                return
            with self._pending_guard:
                waiting = self._pending[session_id]
                job = waiting.popleft() if waiting else None
                if job is None:
                    del self._pending[session_id]

    def _answer_utterance(self, message: Message, utterance: str, lang: str,
                          session_id: Optional[str]) -> None:
        try:
            answered = False
            for chunk in self.natural_language_query(utterance, lang,
                                                     session_id):
                if chunk is None:
                    break
                answered = True
                self.bus.emit(message.reply(
                    "speak", {"utterance": chunk, "lang": lang}))
            if not answered:
                self.bus.emit(message.reply("speak", {
                    "utterance": "The persona could not answer.",
                    "lang": lang}))
        except Exception as exc:
            LOG.exception("error answering utterance")
            self.bus.emit(message.reply(
                "speak", {"utterance": f"Error contacting persona: {exc}",
                          "lang": lang}))
        finally:
            self.bus.emit(message.reply("ovos.utterance.handled", {}))

    def handle_internal_message(self, raw: str) -> None:
        """Send a Layer-1 reply to the connected peers its destination names.

        hivemind-core does not listen on the agent bus. A request from a peer
        has that peer as its ``source``. It is not a reply, so it is never sent
        back.
        """
        message = Message.deserialize(raw)
        destination = message.context.get("destination") or []
        if not isinstance(destination, list):
            destination = [destination]
        clients = dict(self.clients)
        if message.context.get("source") in clients:
            return
        delivered = False
        for peer in destination:
            client = clients.get(peer)
            if client is None:
                continue
            delivered = True
            try:
                client.send(HiveMessage(HiveMessageType.BUS, payload=message,
                                        source_peer=peer, target_peers=[peer]))
            except Exception as exc:
                LOG.warning(f"could not send {message.msg_type} to {peer}: "
                            f"{exc}")
        peer = message.context.get("peer")
        if (not delivered and isinstance(peer, str)
                and message.context.get("source") != peer):
            # HIVEMIND-AGENT-1 section 3.3. The request itself has
            # source == peer and is not a response.
            session = message.context.get("session") or {}
            LOG.warning(f"{message.msg_type} - destination {destination} names "
                        f"no connected peer; response dropped "
                        f"(session {session.get('session_id')})")
