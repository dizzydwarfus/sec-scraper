# Built-in imports
from typing import List

# Third party libraries
from pymongo import MongoClient, ASCENDING
from pymongo import IndexModel
from pymongo.errors import OperationFailure

# Internal imports
from utils._logger import MyLogger


class SECDatabase:
    def __init__(self, connection_string):
        self.scrape_logger = MyLogger(name="MongoDB").scrape_logger
        self.client = MongoClient(connection_string)
        self.db = self.client.SECRawData
        self.tickerdata = self.db.TickerData
        self.tickerfilings = self.db.TickerFilings
        self.sicdb = self.db.SICList
        self.factsdb = self.db.Facts
        self.labelsdb = self.db.Labels

        try:
            self.tickerdata.create_indexes(
                [IndexModel([("cik", ASCENDING)], unique=True)]
            )
        except OperationFailure as e:
            self.scrape_logger.error(e)

        try:
            self.tickerfilings.create_indexes(
                [
                    IndexModel([("accessionNumber", ASCENDING)], unique=True),
                    IndexModel([("form", ASCENDING)]),
                ]
            )
        except OperationFailure as e:
            self.scrape_logger.error(e)

        try:
            self.factsdb.create_indexes(
                [IndexModel([("factId", ASCENDING)], unique=True)]
            )

        except OperationFailure as e:
            self.scrape_logger.error(e)

    @property
    def get_server_info(self):
        return self.client.server_info()

    @property
    def get_collection_names(self):
        return self.db.list_collection_names()

    @property
    def get_tickerdata_index_information(self):
        return self.tickerdata.index_information()

    @property
    def get_tickerfilings_index_information(self):
        return self.tickerfilings.index_information()

    def get_tickerdata(self, cik: str = None, ticker: str = None) -> dict:
        if cik is not None:
            return self.tickerdata.find_one({"cik": cik})
        elif ticker is not None:
            return self.tickerdata.find_one({"tickers": ticker.upper()})

        else:
            raise Exception("Please provide either a CIK or ticker.")

    def get_tickerfilings(
        self, cik: str = None, accession_number: str = None
    ) -> List[dict]:
        if cik is not None:
            return [file for file in self.tickerfilings.find({"cik": cik})]

        elif accession_number is not None:
            return [
                file
                for file in self.tickerfilings.find_one(
                    {"accessionNumber": accession_number}
                )
            ]
        else:
            raise Exception("Please provide either a CIK or accession number.")
