# Built-in Imports
from typing import Union, List
import os

# Internal Imports
from main.ticker import TickerData
from utils._logger import MyLogger


# Implement the FileDownloader class to download files from sec edgar as .txt files.
class FileDownloader:
    def __init__(
        self,
        ticker: str,
    ):
        self.scrape_logger = MyLogger(name="FileDownloader").scrape_logger
        self.ticker = TickerData(ticker)
        self.data_dir = os.getcwd() + "/data"

    def _request_file(self, url: Union[str, List[str]]):
        """
        Download the file from the given url and save it as a .txt file.

        Args:
            url: str: The url to download the file from.

        Returns:
            None
        """
        try:
            # Download the file
            self.scrape_logger.info(f"Downloading file from {url}")
            response = self.ticker._requester.rate_limited_request(
                url=url, headers=self.ticker.sec_headers
            )
            response.raise_for_status()
            return response
        except Exception as e:
            self.scrape_logger.error(f"An error occurred {type(e).__name__}: {e}")
            return None

    def _save_file(self, file_content, folder_path: str, file_path: str):
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        with open(file_path, "wb") as file:
            file.write(file_content.content)
        self.scrape_logger.info(f"File saved to {file_path}")

    def download_filings(
        self,
        form: str = None,
        start: str = None,
        end: str = None,
        directory: str = None,
    ):
        """
        Download the 10-K file from the sec edgar website.

        Args:
            form (str, optional): form to download for. Defaults to None.
            start or end (str, optional): date to search for. Defaults to None. Date format is 'YYYY-MM-DD' / 'YYYY-MM' / 'YYYY'
            directory (str, optional): The directory to save the downloads. Defaults to current directory in a data folder

        Returns:
            None
        """
        filings = self.ticker.search_filings(form=form, start=start, end=end)
        directory = directory if directory is not None else self.data_dir

        for filing in filings:
            folder_path = directory + f"/{self.ticker.ticker}/{filing['form'].upper()}"
            # check if the file already exists
            if os.path.exists(f"{folder_path}/{filing['accessionNumber']}.txt"):
                self.scrape_logger.info(
                    f"File {filing['accessionNumber']}.txt already exists"
                )
                continue
            else:
                content = self._request_file(filing["file_url"])
                self._save_file(
                    file_content=content,
                    folder_path=folder_path,
                    file_path=f"{folder_path}/{filing['accessionNumber']}.txt",
                )
        return None


# TODO: first dump raw .txt files into S3 bucket
# TODO: then store raw processed data into mongodb
