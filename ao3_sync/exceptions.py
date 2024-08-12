class AO3Exception(Exception):
    pass


class LoginError(AO3Exception):
    def __init__(self, message, errors=[]):
        super().__init__(message)
        self.errors = errors


class FailedDownload(AO3Exception):
    def __init__(self, message, errors=[]):
        super().__init__(message)
        self.errors = errors
