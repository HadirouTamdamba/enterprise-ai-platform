"""Platform exception hierarchy.

Every layer raises typed exceptions; the API layer maps them to standardized
error responses without ever exposing stack traces.
"""


class PlatformError(Exception):
    """Base class for all platform errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "Internal error", *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(PlatformError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(PlatformError):
    status_code = 401
    code = "authentication_error"


class AuthorizationError(PlatformError):
    status_code = 403
    code = "authorization_error"


class NotFoundError(PlatformError):
    status_code = 404
    code = "not_found"


class ConflictError(PlatformError):
    status_code = 409
    code = "conflict"


class RateLimitExceededError(PlatformError):
    status_code = 429
    code = "rate_limit_exceeded"


class BusinessRuleViolation(PlatformError):
    status_code = 400
    code = "business_rule_violation"


class ModelInferenceError(PlatformError):
    status_code = 502
    code = "model_inference_error"


class ProviderUnavailableError(ModelInferenceError):
    code = "provider_unavailable"


class RAGRetrievalError(PlatformError):
    status_code = 502
    code = "rag_retrieval_error"


class PromptValidationError(ValidationError):
    code = "prompt_validation_error"


class GuardrailViolation(PlatformError):
    status_code = 400
    code = "guardrail_violation"


class ApprovalRequiredError(PlatformError):
    status_code = 403
    code = "approval_required"
