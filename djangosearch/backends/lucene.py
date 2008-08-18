import os
from itertools import ifilter, islice
from django.conf import settings
from search import query
from djangosearch.results import SearchResults
from djangosearch.query import RELEVANCE, QueryConverter
from djangosearch.backends import base
try:
    import PyLucene
except ImportError, e:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Error loading PyLucene module: %s" % e)

# Rebind a few constants to keep the code compact
STORE_NO = PyLucene.Field.Store.NO
STORE_YES = PyLucene.Field.Store.YES
INDEX_NO = PyLucene.Field.Index.NO
TOKENIZED = PyLucene.Field.Index.TOKENIZED
UN_TOKENIZED = PyLucene.Field.Index.UN_TOKENIZED

# Default field names for "frameworky" fields
MODEL_FIELD = "__model"
IDENTIFIER_FIELD = "__identifier"
CONTENTS_FIELD = "__contents"

class PorterStemmerAnalyzer(object):
    """Simple analyzer based on built-in Lucene objects"""

    def tokenStream(self, fieldName, reader):
        result = PyLucene.StandardTokenizer(reader)
        result = PyLucene.StandardFilter(result)
        result = PyLucene.LowerCaseFilter(result)
        result = PyLucene.PorterStemFilter(result)
        result = PyLucene.StopFilter(result, PyLucene.StopAnalyzer.ENGLISH_STOP_WORDS)
        return result

class SearchEngine(base.SearchEngine):
    
    def __init__(self):
        super(base.SearchEngine, self).__init__()
        self._index = None
        self._index_open_count = 0
    
    def __del__(self):
        self._close_index()
        
    def _open_index(self):
        """
        Open the index. Lucene is lame about performance with potential
        multiple writers, so qwbasically treat open/close index as a stack
        """
        
        if self._index is None:
            # Try to open the index for modifing. If the index doesn't exist, 
            # this will fail, and we'll try again, this time letting PyLucene
            # create the directory.
            analyzer = PorterStemmerAnalyzer()
            try:
                self._index = PyLucene.IndexModifier(settings.SEARCH_INDEX_PATH, analyzer, False)
            except PyLucene.JavaError, e:
                if e.getJavaException().getClass().getName() == "java.io.IOException":
                    self._index = PyLucene.IndexModifier(settings.SEARCH_INDEX_PATH, analyzer, True)
                else:
                    raise
            self._index.setMaxFieldLength(65526) # 64k ought to be enough for anyone...
        self._index_open_count += 1
        
    def _close_index(self):
        """
        Close the index.
        """
        self._index_open_count -= 1
        if self._index_open_count <= 0:
            self._index.close()
            self._index = None

    def update(self, indexer, iterable):
        """Update an index from a queryset."""
        self._open_index()
        
        for o in ifilter(indexer.should_index, iterable):
            # Clear a potential old object out of the index
            self.remove(o)
            
            # Create a new document to index.
            doc = PyLucene.Document()
        
            # Index the model identifier so we can easily deal with only models of a certain type
            doc.add(PyLucene.Field(MODEL_FIELD, str(o._meta), STORE_YES, UN_TOKENIZED))
        
            # Index the "identifier" (app_label.module_name.pk) for this object
            doc.add(PyLucene.Field(IDENTIFIER_FIELD, self.get_identifier(o), STORE_YES, INDEX_NO))
        
            # Index the default content for the object
            # Don't actually store the complete contents; just index them.
            doc.add(PyLucene.Field(CONTENTS_FIELD, indexer.flatten(o), STORE_NO, TOKENIZED))
        
            # Index each field that needs to be individually searchable.
            for (name, value) in indexer.get_field_values(o).items():
                doc.add(PyLucene.Field(name, value, STORE_NO, TOKENIZED))
                
            self._index.addDocument(doc)
        
        self._close_index()
        
    def remove(self, obj):
        """Remove an object from the index."""
        self._open_index()
        term = PyLucene.Term(IDENTIFIER_FIELD, self.get_identifier(obj))
        self._index.deleteDocuments(term)
        self._close_index()
            
    def clear(self, models):
        """Clear the entire index of a certain model."""
        self._open_index()
        for model in models:
            term = PyLucene.Term(MODEL_FIELD, str(model._meta))
            self._index.deleteDocuments(term)
        self._close_index()
        
    def search(self, q, models=None, order_by=RELEVANCE, limit=None, offset=None):
        """Perform a search."""
        original_query = q
        q = query.convert(original_query, LuceneQueryConverter)
        if models:
            models_queries = []
            for m in models:
                if hasattr(m, "_meta"):
                    models_queries.append('%s:"%s"' % (MODEL_FIELD, m._meta))
                else:
                    models_queries.append('%s:"%s"' % (MODEL_FIELD, m))
            q += ' AND (%s)' % (' '.join(models_queries))

        searcher = PyLucene.IndexSearcher(settings.SEARCH_INDEX_PATH)
        analyzer = PorterStemmerAnalyzer()
        compiled_query = PyLucene.QueryParser(CONTENTS_FIELD, analyzer).parse(q)
        
        if order_by is RELEVANCE:
            sort = PyLucene.Sort.RELEVANCE
        else:
            reversed = order_by.startswith('-')
            sort_field = PyLucene.SortField(order_by.lstrip('-'), reversed)
            sort = PyLucene.Sort(sort_field)
            
        hits = searcher.search(compiled_query, sort)
        return self._get_search_results(original_query, hits, limit, offset)
        
    def _get_search_results(self, q, hits, limit, offset):
        """Return a SearchResults object for these hits."""
        iterator = iter(hits)
        if limit is not None and offset is not None:
            iterator = islice(iterator, offset, limit+offset)
        elif limit is not None:
            iterator = islice(iterator, 0, limit)
        elif offset is not None:
            iterator = islice(iterator, offset)
        return SearchResults(q, iterator, self._resolve_hit)
        
    def _resolve_hit(self, hit):
        return hit.get(IDENTIFIER_FIELD).split(".") + [hit.getScore()]
        
class LuceneQueryConverter(QueryConverter):
    # http://lucene.apache.org/java/docs/queryparsersyntax.html
    QUOTES          = '""'
    GROUPERS        = "()"
    OR              = " "
    NOT             = "NOT "
    SEPARATOR       = ' AND '
    FIELDSEP        = ':'