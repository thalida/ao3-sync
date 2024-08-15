class SeriesApi:
    """
    API for handling AO3 series

    Args:
        client (AO3ApiClient): AO3ApiClient instance

    Attributes:
        URL_PATH (str): URL path for series
    """

    URL_PATH: str = "/series"

    def __init__(self, client):
        self._client = client
