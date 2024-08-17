# from ao3_sync.api import AO3ApiClient

# api = AO3ApiClient(
#     username="jessikajones",
#     password='!^}t#hQJ"5zU10:b3c\\9MM',
#     debug=True,
#     use_debug_cache=False,
#     use_history=False,
# )
# # api.series.fetch_works("1492355")
# api.series.sync("1492355")


from enum import Enum


class DownloadFormat(Enum):
    """
    Enum for AO3 download formats

    Attributes:
        HTML (str): HTML
        EPUB (str): EPUB
        MOBI (str): MOBI
        PDF (str): PDF
        AZW3 (str): AZW3
    """

    HTML = "html"
    EPUB = "epub"
    MOBI = "mobi"
    PDF = "pdf"
    AZW3 = "azw3"


def main():
    print(DownloadFormat("html"))


if __name__ == "__main__":
    main()
