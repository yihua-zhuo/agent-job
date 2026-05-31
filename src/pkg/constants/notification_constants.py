"""Notification domain constants."""

from __future__ import annotations

# Valid priority levels for notifications.
VALID_PRIORITIES: frozenset[str] = frozenset({"low", "normal", "high", "urgent"})

# Valid channel values for NotificationModel.channel / notification_type parameter.
# Maps to the channel column; do NOT use to validate a general 'notification_type' concept.
VALID_NOTIFICATION_CHANNELS: frozenset[str] = frozenset({"in_app", "email", "sms", "push"})

# Allowed keys in NotificationModel.payload_params.
# Enforced at insert time by NotificationService.send_notification,
# and again at serialization time by NotificationModel.to_dict().
PAYLOAD_PARAMS_ALLOWED_KEYS: frozenset[str] = frozenset({"content", "related_type", "related_id"})

# Maximum byte size for the serialized notification params JSON payload.
# Set to 4096 to match the practical limit for JSON column storage in PostgreSQL.
NOTIFICATION_PARAMS_MAX_BYTES: int = 4096
