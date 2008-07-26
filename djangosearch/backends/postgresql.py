from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.models.query import EmptyQuerySet

from djangosearch.backends import base
from djangosearch.indexer import get_indexer, get_indexed_models
from djangosearch.query import QueryConverter, convert_new
from djangosearch.results import SearchResult
from djangosearch.utils import slicify

qn = connection.ops.quote_name

if settings.DATABASE_ENGINE != "postgresql":
    raise ImproperlyConfigured('The postgresql search engine requires the postgresql database engine.')

class SearchEngine(base.SearchEngine):
    """
    A PostgreSQL full text search engine.
    """
    def count(self, query, models=None):
        (conv_query, fields) = convert_new(query, PostgresqlQueryConverter)
        if not conv_query:
            return []
        if not models:
            models = get_indexed_models()
        if len(models) == 1:
            return self._get_queryset(models[0], conv_query, fields).count()
        selects = []
        params = []
        for model in models:
            selects.append("""
            (SELECT COUNT(%(pk)s) 
            FROM %(table)s, to_tsquery(%%s) query
            WHERE query @@ %(tsvector)s)
            """ % {
                "pk": qn(model._meta.pk.column),
                "table": qn(model._meta.db_table),
                "tsvector": self._get_tsvector(get_indexer(model).fields)
            })
            params.append(conv_query)
        cursor = connection.cursor()
        cursor.execute("SELECT %s" % " + ".join(selects), params)
        return cursor.fetchone()[0]
        
    def search(self, query, models=None, order_by=["-relevance"], limit=None, offset=None):
        (conv_query, fields) = convert_new(query, PostgresqlQueryConverter)
        if not conv_query:
            return []
        if not models:
            models = get_indexed_models()
        if len(models) == 1:
            qs = self._get_queryset(models[0], conv_query, fields, order_by)
            qs = slicify(qs, limit, offset)
            return [SearchResult(obj, obj.relevance) for obj in qs]
        selects = []
        params = []
        for model in models:
            table = qn(model._meta.db_table)
            selects.append("""
            (SELECT %%s, %%s, %(pk)s, 
                ts_rank_cd(%(tsvector)s, query, 32) as relevance
            FROM %(table)s, to_tsquery(%%s) query
            WHERE query @@ %(tsvector)s)""" % {
                'pk': "%s.%s" % (table, qn(model._meta.pk.column)),
                'table': table,
                'tsvector': self._get_tsvector(get_indexer(model).fields),
            })
            params.extend([
                model._meta.app_label,
                model._meta.object_name,
                conv_query,
            ])
        cursor = connection.cursor()
        sql = "%s ORDER BY relevance DESC" % " UNION ".join(selects)
        if limit:
            sql += " LIMIT %d" % limit
        if offset:
            if limit is None:
                sql += " LIMIT %d" % connection.ops.no_limit_value()
            sql += " OFFSET %d" % offset
        cursor.execute(sql, params)
        return [SearchResult((r[0], r[1], r[2]), r[3]) 
                    for r in cursor.fetchall()]
    
    def _get_queryset(self, model, query=None, fields={}, order_by=None):
        if not query:
            return EmptyQuerySet(model)
        match = "to_tsquery(%%s) @@ %s" % \
                    self._get_tsvector(get_indexer(model).fields)
        return model.objects.extra(
                    select={'relevance': match},
                    select_params=[query],
                    where=[match],
                    params=[query],
                    order_by=order_by)

    def _get_tsvector(self, fields):
        columns = ["coalesce(%s, '')" % qn(s) for s in fields]
        # TODO: support different languages
        return "to_tsvector('english', %s)" % " || ".join(columns)
    
    def update(self, indexer, iterable):
            pass

    def remove(self, obj):
        pass

    def clear(self, models):
        pass
           

class PostgresqlQueryConverter(QueryConverter):
    QUOTES          = "''"
    GROUPERS        = "()"
    OR              = " | "
    NOT             = "!"
    SEPARATOR       = ' & '
    IN_QUOTES_SEP   = ' '
    FIELDSEP        = ':'
