from utils._dataclasses import Facts, Context, LinkLabels


# create class to handle transforming scraped data
# this class should not need to know about the database
# this class should not need to know about scraper mechanism
# the inputs should only be the scraped data
class Processor:
    def __init__(self, facts: list, labels: list, context: list, link_labels: list):
        self.facts = facts
        self.labels = labels
        self.context = context
        self.link_labels = link_labels

    def process_facts(self):
        """Process facts"""
        return [Facts(fact) for fact in self.facts]

    def process_labels(self):
        """Process labels"""
        return [LinkLabels(label) for label in self.labels]

    def process_context(self):
        """Process context"""
        return [Context(context) for context in self.context]

    def process_link_labels(self):
        """Process link labels"""
        return [LinkLabels(link_label) for link_label in self.link_labels]

    def process_all(self):
        """Process all"""
        return (
            self.process_facts(),
            self.process_labels(),
            self.process_context(),
            self.process_link_labels(),
        )
