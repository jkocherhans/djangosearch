"""
A fake backend for mocking during tests.
"""

from djangosearch.backends import SearchEngine as BaseSearchEngine, search

class SearchEngine(BaseSearchEngine):

    def update(self, indexer, iterable):
        pass

    def remove(self, obj):
        pass

    def clear(self, models):
        pass

    def get_results(self, query):
        return []

    def get_count(self, query):
        return 0

