from django.conf import settings
from djangosearch.query import QueryConverter, convert as convert_query
from djangosearch.results import SearchResults, SearchResult
from djangosearch.backends.base import SearchEngine as BaseSearchEngine


class SearchEngine(BaseSearchEngine):
    def get_results(self, query, *args, **kwargs):
        raise NotImplementedError
    
class SphinxQueryConverter(QueryConverter):
    # http://www.sphinxsearch.com/doc.html#extended-syntax
    QUOTES          = '""'
    GROUPERS        = "()"
    OR              = " | "
    NOT             = "-"
    SEPARATOR       = ' '
    FIELDSEP        = ':' # FIXME 