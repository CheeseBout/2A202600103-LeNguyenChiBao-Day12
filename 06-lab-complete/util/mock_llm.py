"""Deterministic mock LLM for local/prod-lab testing."""


def ask(question: str) -> str:
	text = (question or "").strip().lower()
	if not text:
		return "Please provide a question."

	if "docker" in text:
		return "Container is a portable package for app + dependencies: build once, run anywhere."
	if "jwt" in text:
		return "JWT is a signed token carrying claims; server verifies signature and expiry before access."
	if "redis" in text:
		return "Redis is an in-memory data store used here for shared stateless session and limits."

	return "Agent is running in mock mode. Ask about Docker, JWT, Redis, or deployment concepts."
