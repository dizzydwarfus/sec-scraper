from main.ticker import TickerData
from utils._logger import MyLogger


class Scraper:
    def __init__(self, ticker: str, filings: list = None):
        self.ticker = TickerData(ticker)

        self.scrape_logger = MyLogger(name="scraper").scrape_logger

        # initialize state to capture failed filings
        self.failed_filings = []

    def generate_filing_dict(self, filings: dict):
        for filing in filings:
            yield {
                "accessionNumber": filing["accessionNumber"],
                "form": filing["form"],
                "date": filing["date"],
                "cik": self.ticker.cik,
                "ticker": self.ticker.ticker,
            }

    def scrape(self):
        self.scrape_logger.info(f"Scraping {self.ticker.ticker} ({self.ticker.cik})")

        # Scrape facts
        self.scrape_facts()

        # Scrape labels
        self.scrape_labels()

        # Scrape context
        self.scrape_context()

        # Scrape metalinks
        self.scrape_metalinks()

        # Scrape calculations
        self.scrape_calculations()

        # Scrape definitions
        self.scrape_definitions()

    def scrape_facts(self):
        pass

    def scrape_labels(self):
        pass

    def scrape_context(self):
        pass

    def scrape_metalinks(self):
        pass

    def scrape_calculations(self):
        pass

    def scrape_definitions(self):
        pass


# separate classes into scraper, processor, and storer classes
## processor class will handle the processing of the data
## storer class will handle the storing of the data

## TickerData will handle getting the ticker data
### - get filings
### - get submissions
### - filing as list of dict
### - submission as list of dict
### - get submission by accession number
### - get filing by accession number
### - get filing by date
### - get submission by date
### - get filing by form

## scraper class will handle the scraping of the data
### - inject TickerData as dependency
### - scrape facts
### - scrape labels
### - scrape context
### - scrape metalinks
### - scrape calculations
### - scrape definitions

## processor class will handle the processing of the data
### - inject TickerData as dependency
### - inject Scraper as dependency
### - process facts
### - process labels
### - process context
### - combine facts, labels, context

## storer class will handle the storing of the data
### - inject TickerData as dependency
### - inject Scraper as dependency
### - inject Processor as dependency
### - store facts
### - store labels
### - store context
### - store combined data
### - store all data
