"""Application layer: use cases, ports and orchestration.

The application layer coordinates domain rules through ports. API routers should stay thin and
translate HTTP payloads to use-case commands instead of owning business logic.
"""
