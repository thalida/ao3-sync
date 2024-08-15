class SeriesApi:
    URL_PATH: str = "/series"

    def __init__(self, client):
        self._client = client
