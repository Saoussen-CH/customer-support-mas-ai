"""Thin wrapper to expose billing_agent as `agent` for AgentEvaluator."""

from customer_support_agent.agents.billing_agent import billing_agent

agent = billing_agent
