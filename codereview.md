# Architecture & Project Structure

1. Clear project structure (`src/`, `tests/`, `docs/`, `scripts/`)
2. Separation of concerns (business logic vs IO vs API)
3. No circular imports
4. Modules have single responsibility
5. Avoid giant “utility.py” dumping grounds
6. Dependency direction is clean and intentional
7. Config separated from code
8. Environment-specific behavior isolated
9. Entry points are explicit (`main.py`, CLI, app factory)
10. Package boundaries are clear

---

# Readability & Maintainability

11. Variable names are meaningful
12. Function names describe behavior precisely
13. Classes represent real domain concepts
14. No misleading abbreviations
15. Code avoids unnecessary cleverness
16. Comments explain “why”, not “what”
17. Dead code removed
18. Large functions split into smaller units
19. Magic numbers/constants extracted
20. Consistent formatting/style across project

---

# Python-Specific Best Practices

21. Proper use of list/dict/set comprehensions
22. Avoid mutable default arguments
23. Correct context manager usage (`with`)
24. Proper exception hierarchy
25. Avoid bare `except:`
26. Use dataclasses where appropriate
27. Type hints are meaningful and complete
28. Avoid abusing global state
29. Correct async/await usage
30. Avoid unnecessary metaprogramming/reflection

---

# Performance & Scalability

31. No accidental O(N²) or worse loops
32. Database queries are optimized
33. Avoid loading huge files fully into memory
34. Streaming/generator usage where appropriate
35. Caching strategy is justified
36. No repeated expensive computations
37. Concurrency/threading handled safely
38. Async tasks do not block event loop
39. Batch processing used when suitable
40. Profiling evidence exists for “optimized” code

---

# Error Handling & Reliability

41. Errors are logged with useful context
42. Retry logic is bounded and safe
43. External API failures handled gracefully
44. Timeouts exist for network operations
45. Failure paths are tested
46. No silent exception swallowing
47. Cleanup logic exists for partial failures
48. Validation occurs at boundaries
49. Edge cases explicitly considered
50. Application startup failures are understandable

---

# Security

51. Secrets are never hardcoded
52. Input validation/sanitization exists
53. SQL injection protections used
54. Safe deserialization/parsing
55. Dependency vulnerabilities checked
56. Authentication/authorization enforced correctly
57. Sensitive data masked in logs
58. File handling prevents traversal attacks
59. Rate limiting or abuse prevention considered
60. Principle of least privilege followed

---

# Testing

61. Unit tests cover core logic
62. Integration tests exist for critical flows
63. Tests are deterministic
64. Edge cases are tested
65. Failure scenarios are tested
66. Mocking is not excessive
67. Test names clearly explain intent
68. CI automatically runs tests
69. Coverage is meaningful, not vanity metrics
70. Regression tests added for past bugs

---

# DevOps & Deployment

71. Reproducible environments (`requirements.txt`, `poetry.lock`, etc.)
72. Docker images are minimal and secure
73. CI/CD pipelines are stable
74. Health checks/readiness checks exist
75. Logging and monitoring integrated
76. Graceful shutdown supported
77. Configuration documented
78. Versioning/release process defined
79. Rollback strategy exists
80. Observability/tracing included

---

# Data & Database

81. Migrations are version-controlled
82. Schema changes are backward compatible
83. Transactions used correctly
84. Indexes exist for important queries
85. No N+1 query issues
86. Data models are normalized appropriately
87. Data retention policies considered
88. Large blobs/files handled externally when needed
89. Connection pooling configured correctly
90. ORM usage does not hide expensive behavior

---

# API Design

91. APIs are consistent
92. Proper HTTP status codes returned
93. Request/response schemas validated
94. Pagination exists for large datasets
95. API versioning strategy exists
96. Idempotency considered where needed
97. Error responses are structured
98. Backward compatibility maintained
99. Authentication tokens handled securely
100. OpenAPI/Swagger docs maintained

---

# Team & Engineering Quality

101. PR size is reasonable
102. Commit history is meaningful
103. Documentation exists for critical flows
104. Onboarding instructions work
105. Architectural decisions documented
106. Tech debt identified explicitly
107. Linters/type checkers enforced in CI
108. Ownership boundaries are clear
109. Dependencies justified and maintained
110. No copy-paste duplication across modules

---

# Advanced / Senior-Level Review Points

111. Domain model reflects business reality
112. Hidden coupling minimized
113. Failure isolation exists
114. Backpressure/load-shedding considered
115. Resource lifecycle is explicit
116. Eventual consistency issues understood
117. Concurrency hazards analyzed
118. Upgrade/migration paths considered
119. Long-term maintainability prioritized over shortcuts
120. Simplicity preferred unless complexity is justified

---
