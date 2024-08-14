class AO3Exception(Exception):
    """
    Base class for all AO3 exceptions
    """

    pass


class FailedDownload(AO3Exception):
    """
    Raised when a download fails.
    """

    def __init__(self, message, errors=[]):
        super().__init__(message)
        self.errors = errors


class FailedRequest(AO3Exception):
    """
    Generic exception for failed requests.
    """

    def __init__(self, message, errors=[]):
        super().__init__(message)
        self.errors = errors


class LoginError(AO3Exception):
    """
    Raised when the user is not logged in.
    """

    def __init__(self, message, errors=[]):
        super().__init__(message)
        self.errors = errors


class RateLimitError(AO3Exception):
    """
    Raised when the user is rate-limited.
    """

    def __init__(self, message, errors=[]):
        super().__init__(message)
        self.errors = errors
