"""Notification domain constants."""

# Valid priority levels for notifications.
VALID_PRIORITIES = {"low", "normal", "high", "urgent"}

# Column naming convention: the ORM column is named params_ (trailing underscore) to avoid
# shadowing the Python built-in `params`.  When serialized to API responses via to_dict(),
# the value is emitted under the key "params" (no trailing underscore) for clarity.
NOTIFICATION_PARAMS_COLUMN = "params_"
NOTIFICATION_PARAMS_API_KEY = "params"
