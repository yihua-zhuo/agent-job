class ErrorCode:
    """统一错误码"""
    # 通用错误 (1000-1999)
    UNKNOWN = 1000
    INVALID_PARAMS = 1001
    MISSING_PARAMS = 1002

    # 业务错误 (2000-2999)
    CUSTOMER_NOT_FOUND = 2001
    DUPLICATE_EMAIL = 2002

    # 权限错误 (3000-3999)
    UNAUTHORIZED = 3001
    FORBIDDEN = 3002

    # 系统错误 (5000-5999)
    INTERNAL_ERROR = 5000


class AppError(Exception):
    """应用异常"""

    def __init__(self, code, message, status_code=400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)
