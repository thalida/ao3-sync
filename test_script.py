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
