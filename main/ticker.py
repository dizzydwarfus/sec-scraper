# Third-party libraries
import pandas as pd

# Internal imports
from main.sec import SECData
from utils._generic import indexify_url
from utils._requester import RateLimitedRequester
from utils._logger import MyLogger


class TickerData(SECData):
    """
    Inherited from SECData class. Retrieves data from SEC Edgar database based on ticker. Stores ticker data to be used in Scraper.

    url is constructed based on the following: https://www.sec.gov/Archives/edgar/data/{cik}/{ascension_number}/{file_name}

    cik is the CIK number of the company = access via get_ticker_cik

    ascension_number is the accessionNumber column of filings_df

    file name for xml is always '{ticker}-{reportDate}.{extension}
    """

    def __init__(
        self,
        ticker: str,
        requester_company: str = "Financial API",
        requester_name: str = "API Caller",
        requester_email: str = "apicaller@gmail.com",
        taxonomy: str = "us-gaap",
    ):
        super().__init__(
            taxonomy,
        )
        self._requester = RateLimitedRequester(
            requester_company=requester_company,
            requester_name=requester_name,
            requester_email=requester_email,
        )
        self.scrape_logger = MyLogger(name="TickerData").scrape_logger
        self.ticker = ticker.upper()
        self.cik = self.get_ticker_cik(self.ticker)
        self._submissions = self.get_submissions(self.cik)
        self._filings = None
        self._forms = None
        self._index = self.get_cik_index(self.cik)
        self._filing_folder_urls = None
        self._filing_urls = None

    @property
    def submissions(
        self,
    ) -> dict:
        if self._submissions is not None:
            self._submissions["cik"] = self.cik
            self._submissions["filings"] = self.filings.replace({pd.NaT: None}).to_dict(
                "records"
            )
        return self._submissions

    @property
    def filings(
        self,
    ) -> pd.DataFrame:
        if self._filings is None:
            self._filings = self._filings_as_df()
        return self._filings

    @property
    def filings_list(
        self,
    ) -> list:
        return self._filings_as_list()

    @property
    def latest_filing(
        self,
    ) -> pd.DataFrame:
        return self.filings.iloc[0, :].to_dict() if len(self.filings) > 0 else None

    @property
    def latest_10Q(
        self,
    ) -> dict:
        return (
            self.filings.query("form == '10-Q'").iloc[0, :].to_dict()
            if len(self.filings.query("form == '10-Q'")) > 0
            else None
        )

    @property
    def latest_10K(
        self,
    ) -> dict:
        return (
            self.filings.query("form == '10-K'").iloc[0, :].to_dict()
            if len(self.filings.query("form == '10-K'")) > 0
            else None
        )

    @property
    def latest_8K(
        self,
    ) -> dict:
        return (
            self.filings.query("form == '8-K'").iloc[0, :].to_dict()
            if len(self.filings.query("form == '8-K'")) > 0
            else None
        )

    @property
    def filing_folder_urls(
        self,
    ) -> list:
        if self._filing_folder_urls is None:
            self._filing_folder_urls = self._get_filing_folder_urls()
        return self._filing_folder_urls

    @property
    def filing_urls(
        self,
    ) -> list:
        if self._filing_urls is None:
            self._filing_urls = self.filings["file_url"].tolist()

        return self._filing_urls

    @property
    def forms(
        self,
    ) -> list:
        if self._forms is None:
            self._forms = list(set(self.filings["form"]))
            self._forms.sort()
        return self._forms

    def _get_filing_folder_urls(
        self,
    ) -> list:
        """Get filing folder urls from index dict.

        Args:
            index (dict): index dict from get_index method

        Returns:s
            filing_folder_urls (list): list of filing folder urls
        """

        filing_folder_urls = [
            self.BASE_SEC_URL + self._index["directory"]["name"] + "/" + folder["name"]
            for folder in self._index["directory"]["item"]
            if folder["type"] == "folder.gif"
        ]
        return filing_folder_urls

    def search_filings(
        self,
        form: str = None,
        start: str = None,
        end: str = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Search filings based on form, date, period.

        Args:
            form (str, optional): form to search for. Defaults to None.
            start or end (str, optional): date to search for. Defaults to None. Date format is 'YYYY-MM-DD' / 'YYYY-MM' / 'YYYY'
            **kwargs: additional keyword arguments can include any column in the filings DataFrame
        Returns:
            pd.DataFrame: DataFrame containing search results
        """
        query = []
        if form is not None:
            query.append(f"form == '{form.upper()}'")
        if start is not None:
            query.append(f"filingDate >= '{start}'")
        if end is not None:
            query.append(f"filingDate <= '{end}'")
        for key, value in kwargs.items():
            query.append(f"{key} == '{value}'")

        return self.filings.query(" and ".join(query)).to_dict("records")

    def get_filing_folder_index(self, folder_url: str, return_df: bool = True):
        """Get filing folder index from folder url.

        Args:
            folder_url (str): folder url to retrieve data from
            return_df (bool, optional): Whether to return a DataFrame or dict. Defaults to True.

        Returns:
            index (dict): index dict or dataframe
        """
        index_url = indexify_url(folder_url)
        index = self._requester.rate_limited_request(
            index_url, headers=self.sec_headers
        )
        return (
            pd.DataFrame(index.json()["directory"]["item"])
            if return_df
            else index.json()["directory"]["item"]
        )

    def _get_filings(
        self,
    ) -> dict:
        """Get filings and urls to .txt from submissions dict.

        Args:
            submissions (dict): submissions dict from get_submissions method

        Returns:
            filings (dict): dictionary containing filings
        """
        self.scrape_logger.info(f"Making http request for {self.ticker} filings...")
        filings = self._submissions["filings"]["recent"]

        if len(self._submissions["filings"]) > 1:
            self.scrape_logger.info(f"Additional filings found for {self.ticker}...")
            for file in self._submissions["filings"]["files"]:
                additional_filing = self.get_submissions(submission_file=file["name"])
                filings = {
                    key: filings[key] + additional_filing[key] for key in filings.keys()
                }
        return filings

    def _filings_as_df(
        self,
    ) -> pd.DataFrame:
        """Convert filings to DataFrame.

        Returns:
            pd.DataFrame: filings as DataFrame
        """
        filings = pd.DataFrame(self._get_filings())
        # Convert reportDate, filingDate, acceptanceDateTime columns to datetime
        filings["reportDate"] = pd.to_datetime(filings["reportDate"])
        filings["filingDate"] = pd.to_datetime(filings["filingDate"])
        filings["acceptanceDateTime"] = pd.to_datetime(filings["acceptanceDateTime"])
        filings["cik"] = self.cik

        filings = filings.loc[~pd.isnull(filings["reportDate"])]

        # get folder url for each row
        filings["folder_url"] = (
            self.BASE_DIRECTORY_URL
            + self.cik
            + "/"
            + filings["accessionNumber"].str.replace("-", "")
        )

        # get file url for each row
        filings["file_url"] = (
            filings["folder_url"] + "/" + filings["accessionNumber"] + ".txt"
        )

        return filings

    def _filings_as_list(
        self,
    ) -> list:
        """Get filings as list of dictionaries.

        Returns:
            list: list of filings as dictionaries
        """
        return self.filings.to_dict("records")

    def __repr__(self) -> str:
        class_name = type(self).__name__
        # main_attrs = ['ticker', 'cik', 'submissions', 'filings']
        # available_methods = [method_name for method_name in dir(self) if callable(
        #     getattr(self, method_name)) and not method_name.startswith("_")]
        return f"""{class_name}({self.ticker})
    CIK: {self.cik}
    Latest filing: {self.latest_filing['filingDate'].strftime('%Y-%m-%d') if self.latest_filing else 'No filing found'} for Form {self.latest_filing['form'] if self.latest_filing else None}. Access via: {self.latest_filing['folder_url'] if self.latest_filing else None}
    Latest 10-Q: {self.latest_10Q['filingDate'].strftime('%Y-%m-%d') if self.latest_10Q else 'No filing found'}. Access via: {self.latest_10Q['folder_url'] if self.latest_10Q else None}
    Latest 10-K: {self.latest_10K['filingDate'].strftime('%Y-%m-%d') if self.latest_10K else 'No filing found'}. Access via: {self.latest_10K['folder_url'] if self.latest_10K else None}"""

    def __repr_html__(self) -> str:
        # class_name = type(self).__name__
        # main_attrs = ['ticker', 'cik', 'submissions', 'filings']
        # available_methods = [method_name for method_name in dir(self) if callable(
        #     getattr(self, method_name)) and not method_name.startswith("_")]
        latest_filing_date = (
            self.latest_filing["filingDate"].strftime("%Y-%m-%d")
            if self.latest_filing
            else "No filing found"
        )
        latest_filing_form = self.latest_filing["form"] if self.latest_filing else None
        latest_filing_folder_url = (
            self.latest_filing["folder_url"] if self.latest_filing else None
        )
        latest_10Q_date = (
            self.latest_10Q["filingDate"].strftime("%Y-%m-%d")
            if self.latest_10Q
            else "No filing found"
        )
        latest_10Q_folder_url = (
            self.latest_10Q["folder_url"] if self.latest_10Q else None
        )
        latest_10K_date = (
            self.latest_10K["filingDate"].strftime("%Y-%m-%d")
            if self.latest_10K
            else "No filing found"
        )
        latest_10K_folder_url = (
            self.latest_10K["folder_url"] if self.latest_10K else None
        )
        return f"""
        <div style="border: 1px solid #ccc; padding: 10px; margin: 10px;">
            <h3>{self.submissions['name']}</h3>
            <h5>{self.submissions['sicDescription']}</h5>
            <p><strong>Ticker:</strong> {self.ticker}</p>
            <p><strong>CIK:</strong> {self.cik}</p>
            <p><strong>Latest filing:</strong> {latest_filing_date} for Form {latest_filing_form}. Access via: <a href="{latest_filing_folder_url}">{latest_filing_folder_url}</a></p>
            <p><strong>Latest 10-Q:</strong> {latest_10Q_date}. Access via: <a href="{latest_10Q_folder_url}">{latest_10Q_folder_url}</a></p>
            <p><strong>Latest 10-K:</strong> {latest_10K_date}. Access via: <a href="{latest_10K_folder_url}">{latest_10K_folder_url}</a></p>
        </div>
        """
