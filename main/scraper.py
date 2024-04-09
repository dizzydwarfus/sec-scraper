from abc import ABC, abstractmethod
from typing import List, Union
import re

# Third Party Imports
import pandas as pd
from bs4 import BeautifulSoup
from bs4.element import Tag

# Internal Imports
from main.ticker import TickerData
from utils._logger import MyLogger
from utils._generic import convert_keys_to_lowercase
from utils._dataclasses import Facts, Context


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


class Scraper:
    def __init__(
        self,
        ticker: str,
        search_strategy: SearchStrategy = None,
    ):
        self.ticker = TickerData(ticker)
        self.search_strategy = search_strategy
        self.scrape_logger = MyLogger(name="Scraper").scrape_logger
        self._soups = []
        self._all_facts = pd.DataFrame()
        self._all_context = pd.DataFrame()
        self._all_labels = pd.DataFrame()
        self._merged_data = pd.DataFrame()
        self.final_data = None
        self.failed = []

    def get_file_data(self, file_dicts: Union[List[dict], dict], force=False) -> None:
        """Get file data from file url which can be retrieved by calling self.filing_urls property.

        Args:
            file_dicts (str): List of file information in a dictionary format to retrieve data from on the SEC website.
                              Use method self.ticker.search_filings(**kwargs) or self.ticker.filings_list to get list of file_dicts.
                              Properties of self.ticker also returns file dicts. - self.ticker.latest_10K, self.ticker.latest_10Q, etc.
            force (bool): If True, force the scraper to re-request and re-parse the file data. Default is False.

        Returns:
            None
        """
        if isinstance(file_dicts, dict):
            file_dicts = [file_dicts]
        for file_dict in file_dicts:
            file_url = file_dict.get("file_url")
            folder_url = file_dict.get("folder_url")
            accession_number = file_dict.get("accessionNumber")
            try:
                if (
                    len(
                        [
                            soup.get("accession_number")
                            for soup in self._soups
                            if soup.get("accession_number") == accession_number
                        ]
                    )
                    > 0
                    and not force
                ):
                    self.scrape_logger.info(
                        f"File data from {accession_number}: {file_url} already requested and parsed."
                    )
                    continue

                data = self.ticker._requester.rate_limited_request(
                    url=file_url, headers=self.ticker.sec_headers
                )
                soup = BeautifulSoup(data.content, "lxml")
                self.scrape_logger.info(
                    f"Parsed file data from {accession_number}: {file_url} successfully."
                )
                self._soups.append(
                    {
                        "accession_number": accession_number,
                        "soup": soup,
                        "file_url": file_url,
                        "folder_url": folder_url,
                    }
                )

            except Exception as e:
                self.scrape_logger.error(
                    f"Failed to parse file data from {accession_number}: {file_url}. {type(e).__name__}: {e}"
                )
                continue

    # should move get_filing_folder_index outside of function so repeated calls are avoided
    # store index_df with folder_url or accession_number to be used to identify _lab.xml of a specific filing
    def get_elements(
        self, folder_url: str, scrape_file_extension: str = "_lab"
    ) -> pd.DataFrame:
        """Get elements from .xml files from folder_url.

        Args:
            folder_url (str): folder url to retrieve data from
            scrape_file_extension (str): .xml file extension to scrape. Use self.ticker.SCRAPE_FILE_EXTENSION to get list of possible values

        Returns:
            pd.DataFrame: returns a dataframe containing the elements, attributes, text
        """
        index_df = self.ticker.get_filing_folder_index(folder_url)
        xml = index_df.query(f"name.str.contains('{scrape_file_extension}')")
        xml_content = self.ticker._requester.rate_limited_request(
            folder_url + "/" + xml["name"].iloc[0], headers=self.ticker.sec_headers
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
            pattern = self.search_strategy.set_pattern()
        return soup.find_all(re.compile(pattern))

    def set_search_strategy(self, search_strategy: SearchStrategy):
        self.search_strategy = search_strategy

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
            response = self.ticker._requester.rate_limited_request(
                url=metalinks_url, headers=self.ticker.sec_headers
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
                f"Failed to retrieve metalinks from {metalinks_url}. {type(e).__name__}: {e}"
            )
            return None

    def scrape_facts(self):
        if len(self._soups) == 0:
            self.scrape_logger.error(
                "No soups found! Please use method self.get_file_data(file_dicts) first. Use self.ticker.search_filings(form, start,end) to get file_dicts."
            )
            raise Exception(
                "No soups found! Please use method self.get_file_data(file_dicts) first. Use self.ticker.search_filings(form, start,end) to get file_dicts."
            )

        for soup_dict in self._soups:
            if soup_dict.get("soup") is None:
                self.scrape_logger.error(
                    f"No soup found in soup_dict: {soup_dict['accession_number']}"
                )
                continue

            try:  # Scrape facts
                facts_list = []
                soup = soup_dict.get("soup")
                accession_number = soup_dict.get("accession_number")

                facts = self.search_facts(soup=soup)
                for fact_tag in facts:
                    facts_list.append(Facts(fact_tag=fact_tag).to_dict())
                facts_df = pd.DataFrame(facts_list)

                facts_df["accessionNumber"] = accession_number
                self._all_facts = pd.concat(
                    [self._all_facts, facts_df], ignore_index=True
                )
            except Exception as e:
                self.scrape_logger.error(
                    f"Failed to scrape facts for {accession_number}...{type(e).__name__}: {e}"
                )
                self.failed.append(
                    dict(
                        failed_type="facts",
                        accessionNumber=accession_number,
                        error=f"Failed to scrape facts for {accession_number}...{type(e).__name__}: {e}",
                    )
                )
                pass

    def scrape_context(self):
        if len(self._soups) == 0:
            self.scrape_logger.error(
                "No soups found! Please use method self.get_file_data(file_dicts) first. Use self.ticker.search_filings(form, start,end) to get file_dicts."
            )
            raise Exception(
                "No soups found! Please use method self.get_file_data(file_dicts) first. Use self.ticker.search_filings(form, start,end) to get file_dicts."
            )

        for soup_dict in self._soups:
            if soup_dict.get("soup") is None:
                self.scrape_logger.error(
                    f"No soup found in soup_dict: {soup_dict['accession_number']}"
                )
                continue

            try:  # Scrape context
                context_list = []
                soup = soup_dict.get("soup")
                accession_number = soup_dict.get("accession_number")
                contexts = self.search_context(soup=soup)
                for tag in contexts:
                    context_list.append(Context(context_tag=tag).to_dict())
                context_df = pd.DataFrame(context_list).drop_duplicates(
                    subset=["contextId"], keep="first"
                )
                context_df["accessionNumber"] = accession_number
                self._all_context = pd.concat(
                    [self._all_context, context_df], ignore_index=True
                )
            except Exception as e:
                self.scrape_logger.error(
                    f"Failed to scrape contexts for {accession_number}...{type(e).__name__}: {e}"
                )
                self.failed.append(
                    dict(
                        failed_type="contexts",
                        accessionNumber=accession_number,
                        error=f"Failed to scrape contexts for {accession_number}...{type(e).__name__}: {e}",
                    )
                )
                pass

    def scrape_labels(self):
        if len(self._soups) == 0:
            self.scrape_logger.error(
                "No soups found! Please use method self.get_file_data(file_dicts) first. Use self.ticker.search_filings(form, start,end) to get file_dicts."
            )
            raise Exception(
                "No soups found! Please use method self.get_file_data(file_dicts) first. Use self.ticker.search_filings(form, start,end) to get file_dicts."
            )

        for soup_dict in self._soups:
            if soup_dict.get("folder_url") is None:
                self.scrape_logger.error(
                    f"No folder_url found: {soup_dict['accession_number']}"
                )
                continue

            try:  # Scrape labels
                accession_number = soup_dict.get("accession_number")
                folder_url = soup_dict.get("folder_url")
                labels = self.get_elements(
                    folder_url=folder_url,
                    scrape_file_extension="_lab",
                ).query("`xlink:type` == 'resource'")
                labels["xlink:role"] = (
                    labels["xlink:role"].str.split("/").apply(lambda x: x[-1])
                )
                labels["xlink:labelOriginal"] = labels["xlink:label"]
                labels["xlink:label"] = (
                    labels["xlink:label"]
                    .str.replace("(lab_)|(_en-US)", "", regex=True)
                    .str.split("_")
                    .apply(lambda x: ":".join(x[:2]))
                    .str.lower()
                )
                labels["accessionNumber"] = accession_number
                self._all_labels = pd.concat(
                    [self._all_labels, labels], ignore_index=True
                )

            except Exception as e:
                self.scrape_logger.error(
                    f"Failed to scrape labels for {folder_url}...{e}"
                )
                self.failed.append(
                    dict(
                        failed_type="labels",
                        accessionNumber=accession_number,
                        error=f"Failed to scrape labels for {accession_number}...{type(e).__name__}: {e}",
                    )
                )
                pass

    # may not need to implement these methods
    def scrape_metalinks(self):
        pass

    def scrape_calculations(self):
        pass

    def scrape_definitions(self):
        pass

    def merge_data(self):
        self.scrape_logger.info(
            f"Merging facts with context and labels. Current facts length: {len(self._all_facts)}..."
        )
        try:
            self._merged_data = self._all_facts.merge(
                self._all_context,
                how="left",
                left_on=["contextRef", "accessionNumber"],
                right_on=["contextId", "accessionNumber"],
            ).merge(
                self._all_labels.query("`xlink:role` == 'label'"),
                how="left",
                left_on=["factName", "accessionNumber"],
                right_on=["xlink:label", "accessionNumber"],
            )

            self.scrape_logger.info(
                f"Successfully merged facts with context and labels. Merged facts length: {len(self._merged_data)}..."
            )
        except Exception as e:
            self.scrape_logger.error(
                f"Failed to merge facts with context and labels. {type(e).__name__}: {e}"
            )
            self.failed.append(
                dict(
                    failed_type="merge_data",
                    error=f"Failed to merge facts with context and labels. {type(e).__name__}: {e}",
                    accessionNumber=None,
                )
            )
            pass

    def parse_final_df(self):
        self.final_data = self._merged_data.loc[
            ~self._merged_data["labelText"].isnull(),
            [
                "labelText",
                "segment",
                "startDate",
                "endDate",
                "instant",
                "factId",
                "factValue",
                "unitRef",
                "accessionNumber",
            ],
        ].drop_duplicates(subset=["factId", "accessionNumber"])

    def scrape(
        self,
        form: str = None,
        start: str = None,
        end: str = None,
        **kwargs,
    ):
        """Scrape data from SEC website.

        Args:
            form (str, optional): form to search for. Defaults to None.
            start or end (str, optional): date to search for. Defaults to None. Date format is 'YYYY-MM-DD' / 'YYYY-MM' / 'YYYY'
            **kwargs: additional keyword arguments can include any column in the filings DataFrame
        Returns:
            pd.DataFrame: DataFrame containing scraped results
        """
        self.scrape_logger.info(f"Scraping {self.ticker.ticker} ({self.ticker.cik})")

        # Get file data
        self.get_file_data(self.ticker.search_filings(form=form, start=start, end=end))

        # Scrape facts
        self.scrape_facts()

        # Scrape labels
        self.scrape_labels()

        # Scrape context
        self.scrape_context()

        # Merge facts, labels, context
        self.merge_data()

        # Parse final dataframe
        self.parse_final_df()

        self.scrape_logger.info(
            f"Scraping {self.ticker.ticker} ({self.ticker.cik}) complete. Final data length: {len(self.final_data)}"
        )
        return self.final_data


# separate classes into scraper, processor, and storer classes
## processor class will handle the processing of the data
## storer class will handle the storing of the data

## SECData/TickerData will handle getting the ticker data - DONE
### - get filings
### - get submissions
### - filing as list of dict
### - submission as list of dict
### - get filing by accession number - in kwargs
### - get filing by date - in kwargs
### - get filing by form - default argument

## scraper class will handle the scraping of the data - REFACTORING
### - inject TickerData as dependency - DONE
#### scraper needs to get soup object first then pass to scrape methods
# store soup object in class as a list attribute?
# filter filings method to get filings by form, date, accession number
### - scrape facts - DONE
### - scrape labels - DONE
### - scrape context - DONE
### - scrape metalinks
### - scrape calculations
### - scrape definitions

## processor class will handle the processing of the data - NOT YET IMPLEMENTED
### - inject TickerData as dependency
### - inject Scraper as dependency
### - process facts
### - process labels
### - process context
### - combine facts, labels, context

## storer class will handle the storing of the data - NOT YET IMPLEMENTED
### - inject SECdatabase as dependency - DONE
### - store filings - DONE
### - store facts
### - store labels
### - store context
### - store combined data
### - store all data

## SECdatabase class will handle the database connection - DONE


## main class will handle the orchestration of the classes - NOT YET IMPLEMENTED
### - inject TickerData as dependency
### - inject Scraper as dependency
### - inject Processor as dependency
### - inject Storer as dependency
### - scrape data
### - process data
### - store data
### - run all
