# Built-in libraries
import re
from typing import List
from abc import ABC, abstractmethod

# Third-party libraries
import pandas as pd
from bs4 import BeautifulSoup
from bs4.element import Tag

# Internal imports
from main.sec import SECData
from utils._generic import convert_keys_to_lowercase, indexify_url
from utils._requester import RateLimitedRequester
from utils._logger import MyLogger


class SearchStrategy(ABC):
    # set_pattern method must be implemented in inherited classes
    @abstractmethod
    def set_pattern(self) -> str:
        pass


class ContextSearchStrategy(SearchStrategy):
    # set pattern for context search, this is passed into a re.compile method
    # all regex patterns can be used here
    def set_pattern(self) -> str:
        return "context"


class LinkLabelSearchStrategy(SearchStrategy):
    # set pattern for link:label search, this is passed into a re.compile method
    # all regex patterns can be used here
    def set_pattern(self) -> str:
        return "^link:label$"


class FactSearchStrategy(SearchStrategy):
    # set pattern for fact search, this is passed into a re.compile method
    # all regex patterns can be used here
    def set_pattern(self) -> str:
        return "^us-gaap:"


class TickerData(SECData):
    """
    Inherited from SECData class. Retrieves data from SEC Edgar database based on ticker.

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
        search_strategy: SearchStrategy = None,
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
        self.search_strategy = search_strategy
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
            self._filings = self.get_filings()
        return self._filings

    @property
    def latest_filing(
        self,
    ) -> pd.DataFrame:
        return self.filings.iloc[0, :].to_dict() if len(self.filings) > 0 else None

    @property
    def latest_10Q(
        self,
    ) -> pd.DataFrame:
        return (
            self.filings.query("form == '10-Q'").iloc[0, :].to_dict()
            if len(self.filings.query("form == '10-Q'")) > 0
            else None
        )

    @property
    def latest_10K(
        self,
    ) -> pd.DataFrame:
        return (
            self.filings.query("form == '10-K'").iloc[0, :].to_dict()
            if len(self.filings.query("form == '10-K'")) > 0
            else None
        )

    @property
    def latest_8K(
        self,
    ) -> pd.DataFrame:
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
            self._forms = self.filings["form"].unique()
        return self._forms

    def set_search_strategy(self, search_strategy: SearchStrategy):
        self.search_strategy = search_strategy

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

    def get_filings(
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

        filings = pd.DataFrame(filings)
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

    def get_file_data(self, file_url: str) -> BeautifulSoup:
        """Get file data from file url which can be retrieved by calling self.filing_urls property.

        Args:
            file_url (str): File url of .txt file to retrieve data from on the SEC website

        Returns:
            data: File data as a BeautifulSoup object
        """
        data = self._requester.rate_limited_request(
            url=file_url, headers=self.sec_headers
        )
        try:
            soup = BeautifulSoup(data.content, "lxml")
            self.scrape_logger.info(f"Parsed file data from {file_url} successfully.")
            return soup

        except Exception as e:
            self.scrape_logger.error(
                f"Failed to parse file data from {file_url}. Error: {e}"
            )
            raise Exception(f"Failed to parse file data from {file_url}. Error: {e}")

    def get_elements(
        self, folder_url: str, index_df: pd.DataFrame, scrape_file_extension: str
    ) -> pd.DataFrame:
        """Get elements from .xml files from folder_url.

        Args:
            folder_url (str): folder url to retrieve data from
            index_df (pd.DataFrame): dataframe containing files in the filing folder
            scrape_file_extension (str): .xml file extension to scrape

        Returns:
            pd.DataFrame: returns a dataframe containing the elements, attributes, text
        """
        xml = index_df.query(f"name.str.contains('{scrape_file_extension}')")
        xml_content = self._requester.rate_limited_request(
            folder_url + "/" + xml["name"].iloc[0], headers=self.sec_headers
        ).content

        xml_soup = BeautifulSoup(xml_content, "lxml-xml")
        labels = xml_soup.find_all()
        labels_list = []
        for i in labels[1:]:
            label_dict = dict(**i.attrs, labelText=i.text.strip())
            labels_list.append(label_dict)
        return pd.DataFrame(labels_list)

    def search_tags(self, soup: BeautifulSoup, pattern: str = None) -> List[Tag]:
        """Search for tags in BeautifulSoup object. Strategy can be set using self.set_search_strategy method.

        Args:
            soup (BeautifulSoup): BeautifulSoup object
            pattern (str): regex pattern to search for

        Returns:
            soup: BeautifulSoup object
        """
        if self.search_strategy is None and pattern is None:
            raise Exception("Search strategy not set and no pattern provided.")
        if pattern is None:
            pattern = self.search_strategy.get_pattern()
        return soup.find_all(re.compile(pattern))

    # To add more search methods, add a SearchStrategy abstract class with get_pattern method and add a method here
    def search_context(self, soup: BeautifulSoup) -> List[Tag]:
        self.set_search_strategy(ContextSearchStrategy())
        return self.search_tags(soup)

    def search_linklabels(self, soup: BeautifulSoup) -> List[Tag]:
        self.set_search_strategy(LinkLabelSearchStrategy())
        return self.search_tags(soup)

    def search_facts(self, soup: BeautifulSoup) -> List[Tag]:
        self.set_search_strategy(FactSearchStrategy())
        return self.search_tags(soup)

    def get_metalinks(self, metalinks_url: str) -> pd.DataFrame:
        """Get metalinks from metalinks url.

        Args:
            metalinks_url (str): metalinks url to retrieve data from

        Returns:
            df: DataFrame containing metalinks information with columns
            {
                'labelKey': str,
                'localName': str,
                'labelName': int,
                'terseLabel': str,
                'documentation': str,
            }
        """
        try:
            response = self._requester.rate_limited_request(
                url=metalinks_url, headers=self.sec_headers
            ).json()
            metalinks_instance = convert_keys_to_lowercase(response["instance"])
            instance_key = list(metalinks_instance.keys())[0]
            dict_list = []
            for i in metalinks_instance[instance_key]["tag"]:
                dict_list.append(
                    dict(
                        labelKey=i.lower(),
                        localName=metalinks_instance[instance_key]["tag"][i].get(
                            "localname"
                        ),
                        labelName=metalinks_instance[instance_key]["tag"][i]
                        .get("lang")
                        .get("enus")
                        .get("role")
                        .get("label"),
                        terseLabel=metalinks_instance[instance_key]["tag"][i]
                        .get("lang")
                        .get("enus")
                        .get("role")
                        .get("terselabel"),
                        documentation=metalinks_instance[instance_key]["tag"][i]
                        .get("lang")
                        .get("enus")
                        .get("role")
                        .get("documentation"),
                    )
                )

            df = pd.DataFrame.from_dict(dict_list)
            return df
        except Exception as e:
            self.scrape_logger.error(
                f"Failed to retrieve metalinks from {metalinks_url}. Error: {e}"
            )
            return None

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
