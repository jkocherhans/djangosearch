from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.models.query import EmptyQuerySet

from djangosearch.indexer import get_indexer
from djangosearch.query import BaseQueryConverter, convert_new

qn = connection.ops.quote_name

if settings.DATABASE_ENGINE not in ("postgresql", "postgresql_psycopg2"):
    raise ImproperlyConfigured('The postgresql search engine requires the '
                               'postgresql or postgresql_psycopg2 database '
                               'engine.')

def search(query, models=None):
    assert models and len(models) == 1, \
            "This search backend only supports searching single models."
    model = models[0]
    (conv_query, fields) = convert_new(query, QueryConverter)
    # TODO: fields.
    if not conv_query:
        return EmptyQuerySet(model)
    index = get_indexer(model)
    if len(index.text) > 1:
        columns = ["coalesce(%s, '')" % qn(s) for s in index.text]
    else:
        columns = index.text
    # TODO: support different languages
    tsvector = "to_tsvector('english', %s)" % " || ".join(columns)
    return index.get_query_set().extra(
                select={'_relevance': "ts_rank(%s, to_tsquery(%%s), 32)" 
                                        % tsvector},
                select_params=[conv_query],
                where=["to_tsquery(%%s) @@ %s" % tsvector],
                params=[conv_query],
                # FIXME: relevance can't be used outside extra()
                order_by=["-_relevance"])


class QueryConverter(BaseQueryConverter):
    # http://www.postgresql.org/docs/current/static/datatype-textsearch.html
    QUOTES          = "''"
    GROUPERS        = "()"
    OR              = " | "
    NOT             = "!"
    SEPARATOR       = ' & '
    IN_QUOTES_SEP   = ' '
    FIELDSEP        = ':'
