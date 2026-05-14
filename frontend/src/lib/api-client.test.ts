import { describe, it, expect } from "vitest";
import { ApiError } from "./api-client";

describe("ApiError", () => {
  it("constructs with status and message", () => {
    const err = new ApiError(400, "Bad Request");
    expect(err.status).toBe(400);
    expect(err.message).toBe("Bad Request");
    expect(err.name).toBe("ApiError");
    expect(err.body).toBeUndefined();
  });

  it("stores body when provided", () => {
    const body = { detail: "validation failed" };
    const err = new ApiError(422, "Unprocessable Entity", body);
    expect(err.body).toEqual(body);
  });

  describe("isUnauthorized", () => {
    it("returns true for 401", () => {
      expect(new ApiError(401, "Unauthorized").isUnauthorized).toBe(true);
    });
    it("returns false for 403", () => {
      expect(new ApiError(403, "Forbidden").isUnauthorized).toBe(false);
    });
    it("returns false for 404", () => {
      expect(new ApiError(404, "Not Found").isUnauthorized).toBe(false);
    });
    it("returns false for 422", () => {
      expect(new ApiError(422, "Validation Error").isUnauthorized).toBe(false);
    });
  });

  describe("isForbidden", () => {
    it("returns true for 403", () => {
      expect(new ApiError(403, "Forbidden").isForbidden).toBe(true);
    });
    it("returns false for 401", () => {
      expect(new ApiError(401, "Unauthorized").isForbidden).toBe(false);
    });
    it("returns false for 404", () => {
      expect(new ApiError(404, "Not Found").isForbidden).toBe(false);
    });
    it("returns false for 422", () => {
      expect(new ApiError(422, "Validation Error").isForbidden).toBe(false);
    });
  });

  describe("isNotFound", () => {
    it("returns true for 404", () => {
      expect(new ApiError(404, "Not Found").isNotFound).toBe(true);
    });
    it("returns false for 401", () => {
      expect(new ApiError(401, "Unauthorized").isNotFound).toBe(false);
    });
    it("returns false for 403", () => {
      expect(new ApiError(403, "Forbidden").isNotFound).toBe(false);
    });
    it("returns false for 422", () => {
      expect(new ApiError(422, "Validation Error").isNotFound).toBe(false);
    });
  });

  describe("isValidation", () => {
    it("returns true for 422", () => {
      expect(new ApiError(422, "Validation Error").isValidation).toBe(true);
    });
    it("returns false for 401", () => {
      expect(new ApiError(401, "Unauthorized").isValidation).toBe(false);
    });
    it("returns false for 403", () => {
      expect(new ApiError(403, "Forbidden").isValidation).toBe(false);
    });
    it("returns false for 404", () => {
      expect(new ApiError(404, "Not Found").isValidation).toBe(false);
    });
  });
});