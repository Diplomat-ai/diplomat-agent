"""Fixture for testing OpenAI Agents SDK Runner.run_sync detection."""

from agents import Agent, Runner


def run_openai_agent(user_input: str):
    agent = Agent(name="assistant", instructions="You help users.")
    result = Runner.run_sync(agent, user_input)
    return result
