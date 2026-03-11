"""
Load tests — run against staging after deploy to validate SLOs before prod promotion.

Simulates realistic customer support traffic across all agent types.
5 concurrent users, 2 minute run — enough to surface concurrency issues
without burning Agent Engine quota.

Usage:
    locust -f tests/load/locustfile.py \\
      --headless --users 5 --spawn-rate 1 --run-time 2m \\
      --host https://your-service-url \\
      --csv /tmp/load-results --exit-code-on-error 1
"""

import random

from locust import HttpUser, between, task

PRODUCT_QUERIES = [
    "Search for gaming laptops under $1500",
    "Show me wireless headphones",
    "Find me a mechanical keyboard",
    "What tablets do you have?",
    "Search for monitors",
]

ORDER_QUERIES = [
    "Track my order ORD-12345",
    "What is the status of order ORD-67890",
    "Where is my order ORD-11111",
]

BILLING_QUERIES = [
    "I have a question about invoice INV-2025-001",
    "Can you help me understand my bill?",
    "I need help with invoice INV-2024-003",
]

GENERAL_QUERIES = [
    "What is your return policy?",
    "How do I contact support?",
    "What payment methods do you accept?",
]


class CustomerSupportUser(HttpUser):
    """Simulates a realistic customer support conversation."""

    wait_time = between(3, 8)  # Think time between messages (Agent Engine needs breathing room)

    def on_start(self):
        self.user_id = f"load-test-{id(self)}"
        self.session_id = None

    @task(4)
    def product_search(self):
        self.client.post(
            "/api/chat",
            json={
                "message": random.choice(PRODUCT_QUERIES),
                "user_id": self.user_id,
                "session_id": self.session_id,
            },
            timeout=60,
            name="/api/chat [product]",
        )

    @task(3)
    def order_tracking(self):
        self.client.post(
            "/api/chat",
            json={
                "message": random.choice(ORDER_QUERIES),
                "user_id": self.user_id,
                "session_id": self.session_id,
            },
            timeout=60,
            name="/api/chat [order]",
        )

    @task(2)
    def billing_query(self):
        self.client.post(
            "/api/chat",
            json={
                "message": random.choice(BILLING_QUERIES),
                "user_id": self.user_id,
                "session_id": self.session_id,
            },
            timeout=60,
            name="/api/chat [billing]",
        )

    @task(1)
    def general_query(self):
        self.client.post(
            "/api/chat",
            json={
                "message": random.choice(GENERAL_QUERIES),
                "user_id": self.user_id,
                "session_id": self.session_id,
            },
            timeout=60,
            name="/api/chat [general]",
        )

    @task(1)
    def health_check(self):
        self.client.get("/health", name="/health")
