"""Notification domain constants."""

# Valid priority levels for notifications.
VALID_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})

# Valid channel values for NotificationModel.channel / notification_type parameter.
# Maps to the channel column; do NOT use to validate a general 'notification_type' concept.
VALID_NOTIFICATION_CHANNELS = frozenset({"in_app", "email", "sms", "push"})

# Allowed keys in NotificationModel.payload_params.
# Used to structurally reject credential-class or other unexpected fields in to_dict().
# ENFORCEMENT GAP: this constant is currently applied only in to_dict() (serialization),
# not at insert or service input-validation time. Invalid keys are persisted before any
# filtering occurs. If strict enforcement is required at insert time, add a service-layer
# check or a custom Pydantic validator on NotificationCreate that rejects unknown keys.
PAYLOAD_PARAMS_ALLOWED_KEYS = frozenset({"content", "related_type", "related_id"})
