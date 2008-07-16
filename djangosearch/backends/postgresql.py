from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from djangosearch.backends import base
from djangosearch.indexer import get_indexer, get_indexed_models
from djangosearch.models import Document
from djangosearch.query import RELEVANCE, QueryConverter, convert_new
from djangosearch.results import SearchResults

qn = connection.ops.quote_name

class SearchEngine(base.DocumentSearchEngine):
    """
    A PostgreSQL full text search engine.
    """
    
    def __init__(self):
        if settings.DATABASE_ENGINE != "postgresql":
            raise ImproperlyConfigured('The postgresql search engine requires the postgresql database engine.')
    
    def search(self, query, models=None, order_by=RELEVANCE, limit=None, offset=None):
        (conv_query, fields) = convert_new(query, PostgresqlQueryConverter)
        if not conv_query:
            return SearchResults(q, [], 0, lambda x: x)
        if not models:
            models = get_indexed_models()
        doc_table = qn(Document._meta.db_table)
        content_type_match = "%s.%s = %%s" % (doc_table,
                                              qn("content_type_id"))
        content_types = []
        params = []
        for model in models:
            content_types.append(content_type_match)
            params.append(ContentType.objects.get_for_model(model).pk)
        match = "MATCH(%s.%s) AGAINST(%%s IN BOOLEAN MODE)" \
                 % (doc_table, qn("text"))
        sql_order_by = "-relevance" # TODO: fields
        results = Document.objects.extra(
                    select={'relevance': 
                        "ts_rank_cd(to_tsvector(text), to_tsquery(%s), 32)"},
                    select_params=[conv_query],
                    where=["text @@ to_tsquery(%s)",
                           " OR ".join(content_types)],
                    params=[conv_query] + params).order_by(sql_order_by)
        if limit is not None:
            if offset is not None:
                results = results[offset:offset+limit]
            else:
                results = results[:limit]
        return SearchResults(query, results, results.count(), 
                    self._result_callback)
                    

class PostgresqlQueryConverter(QueryConverter):
    QUOTES          = "''"
    GROUPERS        = "()"
    OR              = " | "
    NOT             = "!"
    SEPARATOR       = ' & '
    IN_QUOTES_SEP   = ' '
    FIELDSEP        = ':'
