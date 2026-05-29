"""Notification domain constants."""

# Valid priority levels for notifications.
VALID_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})

# Valid channel/notification_type values.
VALID_NOTIFICATION_TYPES = frozenset({"in_app", "email", "sms", "push", "automation"})
