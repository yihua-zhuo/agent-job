"""Tenant domain constants."""

# Valid plan values for tenant subscriptions.
# NOTE: "pro" is retained as a valid alias for backward compatibility; new callers should use "professional".
VALID_PLANS: frozenset[str] = frozenset({"free", "starter", "pro", "professional", "enterprise"})

__all__ = ["VALID_PLANS"]
