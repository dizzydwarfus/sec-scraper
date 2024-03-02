import datetime as dt
from typing import List, Literal

from pymongo import UpdateOne

from utils.database._connector import SECDatabase
from utils._logger import MyLogger


class Storer:
    def __init__(
        self,
        conn_string: str,
    ) -> None:
        self.scrape_logger = MyLogger(name="storer").scrape_logger

        self.db = SECDatabase(connection_string=conn_string)

    def insert_submission(self, submission: dict):
        """Insert submissions into SEC database. CIK is the primary key.

        Args:
            ticker (TickerData): TickerData object

        Returns:
            str: empty string if successful
            str: ticker's cik if failed
        """
        submission["lastUpdated"] = dt.datetime.now()
        try:
            self.tickerdata.update_one(
                {"cik": submission["cik"]}, {"$set": submission}, upsert=True
            )
            self.scrape_logger.info(
                f'Inserted submissions for {submission["cik"]} into SEC database.'
            )

        except Exception as e:
            self.scrape_logger.error(
                f'Failed to insert submissions for {submission["cik"]} into SEC database. Error: {e}'
            )
            return submission["cik"]
        return None

    def insert_filings(self, cik: str, filings: list):
        """Insert filings into SEC database. Each submission has many filings. Accession number is the primary key.

        Args:
            ticker (TickerData): TickerData object

        Returns:
            str: empty string if successful
            str: ticker's cik if failed
        """
        try:
            for doc in filings:
                doc["lastUpdated"] = dt.datetime.now()

            update_requests = [
                UpdateOne(
                    {"accessionNumber": doc["accessionNumber"]},
                    {"$set": doc},
                    upsert=True,
                )
                for doc in filings
            ]

            self.tickerfilings.bulk_write(update_requests)
            self.scrape_logger.info(f"Sucessfully updated filings for {cik}...")

        except Exception as e:
            self.scrape_logger.error(f"Failed to insert filings for {cik}...{e}")
            return cik
        return None

    def create_update_request(
        self,
        accessionNumber: str,
        items_label: Literal["facts", "labels", "context"],
        items_dict: List[dict],
    ):
        update = UpdateOne(
            {"accessionNumber": accessionNumber},
            {"$set": {items_label: items_dict, "lastUpdated": dt.datetime.now()}},
            upsert=True,
        )
        return update

    def insert_facts(self, accession: str, facts: list):
        """Insert facts into SEC database. Each filing has many facts.

        Args:
            facts (list): A list containing facts for a single filing

        Returns:
            str: empty string if successful
            str: ticker's cik if failed
        """
        try:
            for doc in facts:
                doc["lastUpdated"] = dt.datetime.now()

            fact_update_requests = [
                UpdateOne({"factId": fact["factId"]}, {"$set": fact}, upsert=True)
                for fact in facts
            ]

            self.factsdb.bulk_write(fact_update_requests)
            self.scrape_logger.info(f"Updated facts for {accession}...")

        except Exception as e:
            self.scrape_logger.error(f"Failed to insert facts for {accession}...{e}")
            return accession
        return None
