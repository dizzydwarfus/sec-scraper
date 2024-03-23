# Built-in libraries
import requests
import json

# Third-party libraries
import pandas as pd
from bs4 import BeautifulSoup

# Internal imports
from utils._logger import MyLogger
from utils._requester import RateLimitedRequester


class SECData:
    """Class to retrieve data from SEC Edgar database.

    Args:
        requester_company (str): Name of the requester's company
        requester_name (str): Name of the requester
        requester_email (str): Email of the requester
        taxonomy (str): us-gaap, ifrs-full, dei, or srt

    Raises:
        Exception: If taxonomy is not one of the following: us-gaap, ifrs-full, dei, or srt

    Attributes:
        BASE_API_URL (str): Base url for SEC Edgar database
        US_GAAP_TAXONOMY_URL (str): URL for us-gaap taxonomy
        ALLOWED_TAXONOMIES (list): List of allowed taxonomies
        headers (dict): Headers to be used for API calls
        cik (DataFrame): DataFrame containing CIK and ticker
        tags (list): List of tags in us-gaap taxonomy
        taxonomy (str): us-gaap, ifrs-full, dei, or srt

    Methods:
        get_cik_list: Retrieves the full list of CIK available from SEC database.
        get_ticker_cik: Get a specific ticker's CIK number.
        get_usgaap_tags: Get the list of tags in us-gaap taxonomy.
        get_submissions: Retrieves the list of submissions for a specific CIK.
        get_company_concept: Retrieves the XBRL disclosures from a single company (CIK)
            and concept (a taxonomy and tag) into a single JSON file.
        get_company_facts: Retrieves the XBRL disclosures from a single company (CIK)
            into a single JSON file.
        get_frames: Retrieves one fact for each reporting entity that is last filed that most closely fits the calendrical period requested.
    """

    # Base API URL to request from SEC Edgar database
    BASE_API_URL = "https://data.sec.gov/"
    # Base URL for SEC website
    BASE_SEC_URL = "https://www.sec.gov/"
    # Base directory URL for SEC website, used to get index.json
    BASE_DIRECTORY_URL = "https://www.sec.gov/Archives/edgar/data/"
    # URL to the list of SIC codes
    SIC_LIST_URL = "https://www.sec.gov/corpfin/division-of-corporation-finance-standard-industrial-classification-sic-code-list"
    # URL for us-gaap taxonomy, change the year to get a different version
    US_GAAP_TAXONOMY_URL = "http://xbrl.fasb.org/us-gaap/2024/elts/us-gaap-2024.xsd"
    # URL for srt taxonomy, change the year to get a different version
    SRT_TAXONOMY_URL = "http://xbrl.fasb.org/srt/2024/elts/srt-std-2024.xsd"
    # List of allowed taxonomies
    ALLOWED_TAXONOMIES = {"us-gaap", "ifrs-full", "dei", "srt"}
    # Index file extensions to scrape
    INDEX_EXTENSION = {"-index.html", "-index-headers.html"}
    # Directory index file names
    DIRECTORY_INDEX = {"index.json", "index.xml", "index.html"}
    # File extensions available from the folder directory of a filing folder based on accession number
    FILE_EXTENSIONS = {
        ".xsd",
        ".htm",
        "_cal.xml",
        "_def.xml",
        "_lab.xml",
        "_pre.xml",
        "_htm.xml",
        ".xml",
    }
    # File extensions to scrape for labels, definitions, presentations, and calculations
    SCRAPE_FILE_EXTENSIONS = {"_lab", "_def", "_pre", "_cal"}

    def __init__(
        self,
        requester_company: str = "Financial API",
        requester_name: str = "API Caller",
        requester_email: str = "apicaller@gmail.com",
        taxonomy: str = "us-gaap",
    ):
        # Initialize requester with a method to rate limit requests - 10 requests per second
        self._requester = RateLimitedRequester(
            requester_company=requester_company,
            requester_name=requester_name,
            requester_email=requester_email,
        )

        # Initialize logger, default name of logger is name of logger file
        self.scrape_logger = MyLogger(name="SECScraper").scrape_logger

        # Set headers to be used for API calls
        self.sec_headers = self._requester.sec_headers
        # Set headers to be used for data API calls
        self.sec_data_headers = self._requester.sec_data_headers

        # Initialize attributes that are set in properties
        self._cik_list = None
        self._us_gaap_tags = None
        self._srt_tags = None

        if taxonomy not in self.ALLOWED_TAXONOMIES:
            raise ValueError(
                f"Taxonomy {taxonomy} is not supported. Please use one of the following taxonomies: {self.ALLOWED_TAXONOMIES}"
            )
        self.taxonomy = taxonomy

    @property
    def cik_list(
        self,
    ):
        if self._cik_list is None:
            self._cik_list = self.get_cik_list()
        return self._cik_list

    @property
    def us_gaap_tags(
        self,
    ):
        if self._us_gaap_tags is None:
            self._us_gaap_tags = self.get_tags(xsd_url=self.US_GAAP_TAXONOMY_URL)
            self.us_gaap_tags["id"] = (
                self.us_gaap_tags["id"].str.split("_", n=1).str.join(":").str.lower()
            )
        return self._us_gaap_tags

    @property
    def srt_tags(
        self,
    ):
        if self._srt_tags is None:
            self._srt_tags = self.get_tags(xsd_url=self.SRT_TAXONOMY_URL)
        return self._srt_tags

    def get_cik_list(self):
        """Retrieves the full list of CIK available from SEC database.

        Raises:
            Exception: On failure to retrieve CIK list

        Returns:
            cik_df: DataFrame containing CIK and ticker
        """
        self.scrape_logger.info("Retrieving CIK list from SEC database...")
        url = r"https://www.sec.gov/files/company_tickers.json"
        cik_raw = self._requester.rate_limited_request(url, self.sec_headers)
        cik_json = cik_raw.json()
        cik_df = pd.DataFrame.from_dict(cik_json).T
        return cik_df

    def get_ticker_cik(
        self,
        ticker: str,
    ):
        """Get a specific ticker's CIK number.
        CIK########## is the entity's 10-digit Central Index Key (CIK).

        Args:
            ticker (str): public ticker symbol of the company

        Returns:
            cik: CIK number of the company excluding the leading 'CIK'
        """
        ticker_cik = self.cik_list.query(f"ticker == '{ticker.upper()}'")["cik_str"]
        cik = f"{ticker_cik.iloc[0]:010d}"
        return cik

    def get_tags(self, xsd_url: str = US_GAAP_TAXONOMY_URL):
        """Get the list of tags (elements) in us-gaap taxonomy or provide a different xsd_url to get tags from a different taxonomy.

        Returns:
            list of tags
        """
        url = requests.get(xsd_url).content
        us_gaap_df = pd.DataFrame(
            [
                element.attrs
                for element in BeautifulSoup(url, "lxml-xml").find_all("xs:element")
            ]
        )

        return us_gaap_df

    def get_submissions(self, cik: str = None, submission_file: str = None) -> dict:
        if cik is not None:
            url = f"{self.BASE_API_URL}submissions/CIK{cik}.json"
        elif submission_file is not None:
            url = f"{self.BASE_API_URL}submissions/{submission_file}"
        else:
            raise Exception("Please provide either a CIK number or a submission file.")

        self.scrape_logger.info(
            f"Retrieving submissions of {cik if cik is not None else submission_file} from {url}..."
        )
        response = self._requester.rate_limited_request(
            url, headers=self.sec_data_headers
        )
        data = json.loads(response.text)
        return data

    def get_company_concept(
        self,
        cik: str,
        tag: str,
        taxonomy: str = "us-gaap",
    ):
        """The company-concept API returns all the XBRL disclosures from a single company (CIK)
        and concept (a taxonomy and tag) into a single JSON file, with a separate array of facts
        for each units on measure that the company has chosen to disclose
        (e.g. net profits reported in U.S. dollars and in Canadian dollars).

        Args:
            cik (str): CIK number of the company. Get the list using self.cik
            taxonomy (str): us-gaap, ifrs-full, dei, or srt
            tag (str): taxonomy tag (e.g. Revenue, AccountsPayableCurrent). See full list from https://xbrl.fasb.org/us-gaap/2023/elts/us-gaap-2023.xsd

        Raises:
            Exception: On failure to retrieve company concept either due to invalid CIK, taxonomy, or tag

        Returns:
            data: JSON file containing all the XBRL disclosures from a single company (CIK)
        """
        url = (
            f"{self.BASE_API_URL}api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json"
        )
        response = self._requester.rate_limited_request(
            url, headers=self.sec_data_headers
        )
        data = json.loads(response.text)
        return data

    def get_company_facts(self, cik):
        url = f"{self.BASE_API_URL}api/xbrl/companyfacts/CIK{cik}.json"
        response = self._requester.rate_limited_request(
            url, headers=self.sec_data_headers
        )

        data = json.loads(response.text)
        return data

    def get_frames(self, taxonomy, tag, unit, period):
        """The xbrl/frames API aggregates one fact for each reporting entity that is last filed that most closely fits the calendrical period requested.
        This API supports for annual, quarterly and instantaneous data: https://data.sec.gov/api/xbrl/frames/us-gaap/AccountsPayableCurrent/USD/CY2019Q1I.json

        Args:
            taxonomy (str): us-gaap, ifrs-full, dei, or srt
            tag (str): taxonomy tag (e.g. Revenue, AccountsPayableCurrent). See full list from https://xbrl.fasb.org/us-gaap/2023/elts/us-gaap-2023.xsd
            unit (str): USD, USD-per-shares, etc.
            period (str): CY#### for annual data (duration 365 days +/- 30 days), CY####Q# for quarterly data (duration 91 days +/- 30 days), CY####Q#I for instantaneous data

        Raises:
            Exception: (placeholder)

        Returns:
            data: json formatted response
        """
        url = (
            f"{self.BASE_API_URL}api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json"
        )
        response = self._requester.rate_limited_request(
            url, headers=self.sec_data_headers
        )
        data = json.loads(response.text)
        return data

    def get_data_as_dataframe(
        self,
        cik: str,
    ):
        """Retrieves the XBRL disclosures from a single company (CIK) and returns it as a pandas dataframe.

        Args:
            cik (str): CIK number of the company. Get the list using self.cik

        Returns:
            df: pandas dataframe containing the XBRL disclosures from a single company (CIK)
        """
        data = self.get_company_facts(cik)

        df = pd.DataFrame()

        for tag in data["facts"][self.taxonomy]:
            facts = data["facts"]["us-gaap"][tag]["units"]
            unit_key = list(facts.keys())[0]
            temp_df = pd.DataFrame(facts[unit_key])
            temp_df["label"] = tag
            df = pd.concat([df, temp_df], axis=0, ignore_index=True)
        df = df.astype(
            {
                "val": "float64",
                "end": "datetime64[ns]",
                "start": "datetime64[ns]",
                "filed": "datetime64[ns]",
            }
        )
        df["Months Ended"] = (df["end"] - df["start"]).dt.days.div(30.4375).round(0)
        return df

    def get_cik_index(
        self,
        cik: str = None,
    ) -> dict:
        """Each CIK directory and all child subdirectories contain three files to assist in
        automated crawling of these directories.
        These are not visible through directory browsing.
            - index.html (the web browser would normally receive these)
            - index.xml (a XML structured version of the same content)
            - index.json (a JSON structured vision of the same content)

        Args:
            cik (str): CIK number of the company. Get the list using self.cik

        Returns:
            json: pandas dataframe containing the XBRL disclosures from a single company (CIK)
        """
        cik = cik if cik is not None else self.cik
        url = self.BASE_DIRECTORY_URL + cik + "/" + "index.json"

        self.scrape_logger.info(f"Retrieving index file of {cik} from {url}...")
        response = self._requester.rate_limited_request(url, headers=self.sec_headers)
        return response.json()

    def get_sic_list(self, sic_list_url: str = SIC_LIST_URL) -> dict:
        """Get the list of SIC codes from SEC website.

        Args:
            sic_list_url (str): URL to the list of SIC codes

        Returns:
            pd.DataFrame: DataFrame containing the SIC codes and descriptions
        """
        self.scrape_logger.info(f"Retrieving SIC list from {sic_list_url}...")
        response = self._requester.rate_limited_request(
            sic_list_url, headers=self.sec_headers
        )

        soup = BeautifulSoup(response.content, "lxml")
        sic_table = soup.find("table", {"class": "list"})
        sic_list = []
        for row in sic_table.find_all("tr")[1:]:
            sic_dict = {"_id": None, "Office": None, "Industry Title": None}
            sic_dict["_id"] = row.text.split("\n")[1]
            sic_dict["Office"] = row.text.split("\n")[2]
            sic_dict["Industry Title"] = row.text.split("\n")[3]
            sic_list.append(sic_dict)

        return sic_list
