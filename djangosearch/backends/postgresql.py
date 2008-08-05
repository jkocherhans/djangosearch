from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.models.query import EmptyQuerySet

from djangosearch.backends import base
from djangosearch.indexer import get_indexer
from djangosearch.query import QueryConverter, convert_new

qn = connection.ops.quote_name

if settings.DATABASE_ENGINE != "postgresql":
    raise ImproperlyConfigured('The postgresql search engine requires the postgresql database engine.')

class SearchEngine(base.SearchEngine):
    """
    A PostgreSQL full text search engine.
    """
    def search(self, query, models=None):
        assert models and len(models) == 1, \
                "This search backend only supports searching single models."
        model = models[0]
        (conv_query, fields) = convert_new(query, PostgresqlQueryConverter)
        # TODO: fields.
        if not conv_query:
            return EmptyQuerySet(model)
        columns = get_indexer(model).fields
        if len(columns) > 1:
            columns = ["coalesce(%s, '')" % qn(s) for s in columns]
        # TODO: support different languages
        tsvector = "to_tsvector('english', %s)" % " || ".join(columns)
        return model.objects.extra(
                    select={'relevance': "ts_rank(%s, to_tsquery(%%s), 32)" 
                                            % tsvector},
                    select_params=[conv_query],
                    where=["to_tsquery(%%s) @@ %s" % tsvector],
                    params=[conv_query],
                    # FIXME: relevance can't be used outside extra()
                    order_by=["-relevance"])


class PostgresqlQueryConverter(QueryConverter):
    # http://www.postgresql.org/docs/current/static/datatype-textsearch.html
    QUOTES          = "''"
    GROUPERS        = "()"
    OR              = " | "
    NOT             = "!"
    SEPARATOR       = ' & '
    IN_QUOTES_SEP   = ' '
    FIELDSEP        = ':'
