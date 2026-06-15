from app.services.agent_adapters import AgentAdapter, ClaudeCampaignAgentAdapter, ClaudeHotspotAgentAdapter


AGENTS: dict[str, AgentAdapter] = {
    "agent_1": ClaudeHotspotAgentAdapter(
        name="agent_1",
        display_name="Agent 1",
        description="Claude-powered hotspot operations brief generator.",
    ),
    "agent_2": ClaudeCampaignAgentAdapter(
        name="agent_2",
        display_name="Agent 2",
        description="Claude-powered campaign strategy generator.",
    ),
    "agent_3": AgentAdapter(
        name="agent_3",
        display_name="Agent 3",
        description="Placeholder adapter for the third existing Python agent.",
    ),
}


def list_agents():
    return [adapter.info() for adapter in AGENTS.values()]


def get_agent(name: str) -> AgentAdapter | None:
    return AGENTS.get(name)
