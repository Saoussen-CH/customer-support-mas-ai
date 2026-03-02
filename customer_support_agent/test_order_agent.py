"""Thin wrapper to expose order_agent as `agent` for AgentEvaluator."""

from customer_support_agent.agents.order_agent import order_agent

agent = order_agent
