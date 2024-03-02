import requests
from ratelimit import limits, sleep_and_retry

from utils._logger import MyLogger


class RateLimitedRequester:
    def __init__(
        self,
        requester_company: str,
        requester_name: str,
        requester_email: str,
    ) -> None:
        self.scrape_logger = MyLogger().scrape_logger
        self.requester_company = requester_company
        self.requester_name = requester_name
        self.requester_email = requester_email

    @property
    def sec_headers(self) -> dict:
        """Headers for SEC.gov requests.

        Returns:
            dict: Headers for SEC.gov requests
        """
        return {
            "User-Agent": f"{self.requester_company} {self.requester_name} {self.requester_email}",
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        }

    @property
    def sec_data_headers(self) -> dict:
        """Headers for SEC Edgar database requests.

        Returns:
            dict: Headers for SEC Edgar database requests
        """
        return {
            "User-Agent": f"{self.requester_company} {self.requester_name} {self.requester_email}",
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }

    @sleep_and_retry
    @limits(calls=10, period=1)
    def rate_limited_request(self, url: str, headers: dict):
        """Rate limited request to SEC Edgar database.

        Args:
            url (str): URL to retrieve data from
            headers (dict): Headers to be used for API calls

        Returns:
            response: Response from API call
        """
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        self.scrape_logger.info(f"""Request successful at URL: {url}""")
        return response
