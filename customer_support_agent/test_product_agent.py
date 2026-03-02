"""Thin wrapper to expose product_agent as `agent` for AgentEvaluator."""

from customer_support_agent.agents.product_agent import product_agent

agent = product_agent
