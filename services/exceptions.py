class ExternalServiceError(RuntimeError):
    """Raised when an upstream service or required service config fails."""

    def __init__(self, service: str, message: str, status_code: int = 503):
        super().__init__(message)
        self.service = service
        self.status_code = status_code
