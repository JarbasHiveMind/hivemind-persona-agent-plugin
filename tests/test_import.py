def test_is_agent_protocol_subclass():
    from hivemind_plugin_manager.protocols import AgentProtocol
    from hivemind_persona_agent_plugin import PersonaAgentProtocol
    assert issubclass(PersonaAgentProtocol, AgentProtocol)


def test_implements_mandatory_nlq():
    # the streaming abc method is satisfied (class is concrete/instantiable)
    from hivemind_persona_agent_plugin import PersonaAgentProtocol
    assert "natural_language_query" not in getattr(
        PersonaAgentProtocol, "__abstractmethods__", set())
