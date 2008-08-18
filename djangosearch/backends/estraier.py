from datetime import datetime
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from djangosearch.backends import base
from djangosearch.results import SearchResults
from djangosearch.query import QueryConverter
import httplib2

# http://pypi.python.org/pypi/hyperestraier
from hyperestraier import Node, Document, Condition

CT_ATTR = 'django_ct'
ID_ATTR = 'django_id'


from django.db import models
NUM_SORTED_FIELD_TYPES = [
    models.IntegerField,
    models.DateField, models.DateTimeField, models.TimeField
    ]

ASCENDING = 'A'
DECENDING = 'D'
NUM = 'NUM'
STR = 'STR'
NUMEQ = 'NUMEQ'
STREQ = 'STREQ'

def django_ct(obj):
    """Returns app_label.model_name for the given object or model class."""
    return "%s.%s" % (obj._meta.app_label, obj._meta.module_name)

class SearchEngine(base.SearchEngine):
    """
    A search engine that connects to a Hyperestraier P2P server.
    """
    def __init__(self,):
        # TODO: make node configurable at some point. maybe one per model as a default.
        # for now, we just use a single node for all indexing.
        node_uri = '%s/node/%s' % (settings.HYPERESTRAIER_MASTER, settings.HYPERESTRAIER_NODE)
        self.node = Node()
        self.node.set_url(node_uri)
        self.node.set_auth(settings.HYPERESTRAIER_USER, settings.HYPERESTRAIER_PASSWORD)

    def get_identifier(self, obj):
        """
        Get an unique identifier for the object.

        Use a URI for now since it's easy to look up documents that way.
        http://{app_name}/{module_name}/{id}
        """
        # XXX: hackish. I don't really want to think of a better way right now.
        # we *may* be able to subclass hyperestraier.Node and add a method to
        # easily look up objects by app_label.model_name.pk
        return "est://%s/%s/%s" % (obj._meta.app_label, obj._meta.module_name, obj._get_pk_val())

    def update(self, indexer, iterable):
        for obj in iterable:
            uri = self.get_identifier(obj)
            # AFAICT hyperestraier does not let you update indexed text, just
            # attributes, so delete the old doc if it exists. We'll create
            # one from scratch below. node.edit_doc only updates attributes.
            old_doc = self.node.get_doc_by_uri(uri)
            if old_doc:
                self.node.out_doc_by_uri(uri)
            doc = Document()
            doc.add_attr('@uri', uri) # @uri is required.
            doc.add_attr(CT_ATTR, django_ct(obj))
            doc.add_attr(ID_ATTR, str(obj._get_pk_val()))
            # hyperestraier has something about using add_text for each sentence,
            # so this may not be working correctly yet.
            doc.dtexts = []
            doc.add_text(indexer.flatten(obj))
            # Index field values
            for name, value in indexer.get_field_values(obj).items():
                doc.add_attr(name, value)
            # print out the doc that's getting posted to hyperestraier cause
            # it's nice to see while I'm still developing
            #print doc.dump_draft()
            self.node.put_doc(doc)

    def remove(self, obj):
        """Remove an object from its node."""
        uri = self.get_identifier(obj)
        self.node.out_doc_by_uri(uri)

    def clear(self, models):
        # TODO: this clears the entire index w/o regard to which models were passed in
        # The python hyperestraier library doesn't have a way to clear a node.
        # The hyperestraier P2P server let's you do it via http though.
        uri = '%s/master?action=nodeclr&name=%s' % (settings.HYPERESTRAIER_MASTER, settings.HYPERESTRAIER_NODE)
        http = httplib2.Http()
        http.add_credentials(settings.HYPERESTRAIER_USER, settings.HYPERESTRAIER_PASSWORD)
        response, content = http.request(uri)

    def prep_value(self, db_field, value):
        """
        Hook to give the backend a chance to prep an attribute value before
        sending it to the search engine. By default, just return str(value).
        """
        if isinstance(value, datetime):
            # hyperestraier doesn't quite accept ISO formatted dates :(
            return value.strftime('%Y/%m/%d %H:%M:%S')
        return str(value)

    def _result_callback(self, result_doc):
        """
        Extract and return (app_label, model_name, pk, score) for the given
        hyperestraier.ResultDocument.
        """
        # hyperestraier doesn't return scores for search hits, so return 0
        app_label, model_name = result_doc.attr(CT_ATTR).split('.')
        return (app_label, model_name, result_doc.attr(ID_ATTR), 0)

    def _build_order_clause(self, model, order_by):
        """
        Returns a hyperestraier query clause such as 'fieldname STRA'.
        """
        # Hyperestraier needs to know whether you want to compare field values
        # numerically or as strings when your sort by something other than
        # relevance.
        if order_by[0] == '-':
            order = DECENDING
            field_name = order_by[1:]
        else:
            order = ASCENDING
            field_name = order_by
        if model._meta.get_field(field_name) in NUM_SORTED_FIELD_TYPES:
            data_type = NUM
        else:
            data_type = STR
        return '%s %s%s' % (field_name, data_type, order)

    def _get_eq_operator(self, model, field_name):
        """
        Retruns the appropriate hyperestraier "equals" operator for field_name.
        """
        if model._meta.get_field(field_name) in NUM_SORTED_FIELD_TYPES:
            return NUMEQ
        return STREQ

    def search(self, query, models=None, order_by=RELEVANCE, limit=25, offset=0):
        model = models[0]
        cond = Condition()
        cond.set_phrase(query)

        for field, value in attrs.items():
            operator = self._get_eq_operator(model, field)
            attr_clause = '%s %s %s' % (field, operator, value)
            cond.add_attr(attr_clause)

        # restrict the search results to the given models
        models_clause = ' '.join([django_ct(model) for model in models])
        model_clause = '%s STROREQ %s' % (CT_ATTR, models_clause)
        cond.add_attr(model_clause)

        # handle ordering of the search results
        if order_by != RELEVANCE:
            cond.set_order(self._build_order_clause(model, order_by))

        cond.set_max(limit)
        cond.set_skip(offset)
        node_result = self.node.search(cond)
        return SearchResults(query, node_result.docs, self._result_callback)

class HyperestraierQueryConverter(QueryConverter):
    QUOTES          = '""'
    GROUPERS        = "()"
    OR              = " "
    NOT             = "NOT "
    SEPARATOR       = ' AND '
    FIELDSEP        = ':'
