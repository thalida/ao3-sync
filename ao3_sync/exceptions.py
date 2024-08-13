class AO3Exception(Exception):
    pass


class LoginError(AO3Exception):
    """
    Raised when the user is not logged in.
    """

    def __init__(self, message, errors=[]):
        super().__init__(message)
        self.errors = errors


class FailedDownload(AO3Exception):
    """
    Raised when a download fails.
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
