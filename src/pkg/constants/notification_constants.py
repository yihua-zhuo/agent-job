"""Notification domain constants."""

# Valid priority levels for notifications.
VALID_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})

# Valid channel/notification_type values (action categories belong in automation_constants).
VALID_NOTIFICATION_TYPES = frozenset({"in_app", "email", "sms", "push"})

# Allowed keys in NotificationModel.payload_params.
# Used to structurally reject credential-class or other unexpected fields in to_dict().
PAYLOAD_PARAMS_ALLOWED_KEYS = frozenset({"content", "related_type", "related_id"})
