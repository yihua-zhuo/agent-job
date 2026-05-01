"""Tests for response model."""
import pytest
from datetime import datetime
from models.response import (
    ApiResponse, ApiError, PaginatedData, ResponseStatus, ErrorCode
)


class TestPaginatedData:
    """Tests for PaginatedData class."""

    def test_has_next_when_page_less_than_total_pages(self):
        """Line 77: has_next returns True when page < total_pages."""
        data = PaginatedData(items=[], total=100, page=1, page_size=10, total_pages=10)
        assert data.has_next is True

    def test_has_next_when_page_equals_total_pages(self):
        """Line 77: has_next returns False when page >= total_pages."""
        data = PaginatedData(items=[], total=100, page=10, page_size=10, total_pages=10)
        assert data.has_next is False

    def test_has_prev_when_page_greater_than_one(self):
        """Line 81: has_prev returns True when page > 1."""
        data = PaginatedData(items=[], total=100, page=2, page_size=10, total_pages=10)
        assert data.has_prev is True

    def test_has_prev_when_page_equals_one(self):
        """Line 81: has_prev returns False when page <= 1."""
        data = PaginatedData(items=[], total=100, page=1, page_size=10, total_pages=10)
        assert data.has_prev is False


class TestApiResponseToDict:
    """Tests for ApiResponse.to_dict() method."""

    def test_to_dict_with_data_having_to_dict(self):
        """Lines 149-151: data with to_dict method is called."""
        class MockData:
            def to_dict(self):
                return {"key": "value"}
        
        response = ApiResponse(
            status=ResponseStatus.SUCCESS,
            data=MockData()
        )
        result = response.to_dict()
        assert result["data"] == {"key": "value"}

    def test_to_dict_with_plain_data(self):
        """Lines 152-153: plain data without to_dict is returned as-is."""
        response = ApiResponse(
            status=ResponseStatus.SUCCESS,
            data={"plain": "dict"}
        )
        result = response.to_dict()
        assert result["data"] == {"plain": "dict"}

    def test_to_dict_with_errors(self):
        """Lines 154-158: errors list is serialized."""
        error = ApiError(code=1001, message="Invalid", field="email")
        response = ApiResponse(
            status=ResponseStatus.ERROR,
            errors=[error]
        )
        result = response.to_dict()
        assert "errors" in result
        assert result["errors"][0]["code"] == 1001
        assert result["errors"][0]["message"] == "Invalid"
        assert result["errors"][0]["field"] == "email"

    def test_to_dict_with_meta(self):
        """Lines 159-160: meta dict is included."""
        response = ApiResponse(
            status=ResponseStatus.SUCCESS,
            meta={"page": 1}
        )
        result = response.to_dict()
        assert result["meta"] == {"page": 1}

    def test_to_dict_with_request_id(self):
        """Lines 161-162: request_id is included when present."""
        response = ApiResponse(
            status=ResponseStatus.SUCCESS,
            request_id="req-123"
        )
        result = response.to_dict()
        assert result["request_id"] == "req-123"

    def test_to_dict_timestamp_always_present(self):
        """Line 147: timestamp is always in result."""
        response = ApiResponse(status=ResponseStatus.SUCCESS)
        result = response.to_dict()
        assert "timestamp" in result


class TestApiResponseToJson:
    """Tests for ApiResponse.to_json() method."""

    def test_to_json_returns_valid_json(self):
        """Line 167: to_json produces valid JSON string."""
        response = ApiResponse(
            status=ResponseStatus.SUCCESS,
            message="OK"
        )
        json_str = response.to_json()
        parsed = __import__('json').loads(json_str)
        assert parsed["status"] == "success"
        assert parsed["message"] == "OK"


class TestApiResponseSuccess:
    """Tests for ApiResponse.success() class method."""

    def test_success_response(self):
        """Basic success response creation works."""
        response = ApiResponse.success(data={"id": 1})
        assert response.status == ResponseStatus.SUCCESS
        assert response.data == {"id": 1}


class TestApiResponseError:
    """Tests for ApiResponse.error() class method."""

    def test_error_response_with_status_mapping(self):
        """Error status mapping for various codes."""
        # 1401 -> UNAUTHORIZED
        response = ApiResponse.error("unauthorized", code=1401)
        assert response.status == ResponseStatus.UNAUTHORIZED

        # 1403 -> FORBIDDEN
        response = ApiResponse.error("forbidden", code=1403)
        assert response.status == ResponseStatus.FORBIDDEN

        # 1404 -> NOT_FOUND
        response = ApiResponse.error("not found", code=1404)
        assert response.status == ResponseStatus.NOT_FOUND

        # 1001 -> VALIDATION_ERROR
        response = ApiResponse.error("validation error", code=1001)
        assert response.status == ResponseStatus.VALIDATION_ERROR

        # 1500 -> SERVER_ERROR
        response = ApiResponse.error("server error", code=1500)
        assert response.status == ResponseStatus.SERVER_ERROR

        # 2001 -> NOT_FOUND (USER_NOT_FOUND)
        response = ApiResponse.error("user not found", code=2001)
        assert response.status == ResponseStatus.NOT_FOUND

        # 3001 -> NOT_FOUND (RESOURCE_NOT_FOUND)
        response = ApiResponse.error("resource not found", code=3001)
        assert response.status == ResponseStatus.NOT_FOUND

    def test_error_response_default_status(self):
        """Default ERROR status for unknown codes."""
        response = ApiResponse.error("unknown error", code=9999)
        assert response.status == ResponseStatus.ERROR