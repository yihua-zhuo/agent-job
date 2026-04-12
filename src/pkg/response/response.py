class Response:
    """统一响应"""

    @staticmethod
    def success(data=None, message="success"):
        return {"code": 0, "message": message, "data": data}

    @staticmethod
    def error(code, message):
        return {"code": code, "message": message, "data": None}
