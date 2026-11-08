"""One error format for the whole API."""


class AirlockError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str = ""):
        self.message = message or self.code
        super().__init__(self.message)


class Unauthorized(AirlockError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AirlockError):
    status_code = 403
    code = "forbidden"


class ToolForbidden(Forbidden):
    code = "tool_forbidden"


class NotFound(AirlockError):
    status_code = 404
    code = "not_found"


class ValidationFailed(AirlockError):
    status_code = 422
    code = "validation_error"


class InvalidPRUrl(ValidationFailed):
    code = "invalid_pr_url"


class PolicyViolation(ValidationFailed):
    code = "policy_violation"


class RateLimited(AirlockError):
    status_code = 429
    code = "rate_limited"


class Unavailable(AirlockError):
    status_code = 503
    code = "unavailable"


class QueueFull(Unavailable):
    code = "queue_full"
