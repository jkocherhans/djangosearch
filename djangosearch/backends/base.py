from django.contrib.contenttypes.models import ContentType
from django.utils.encoding import force_unicode
from django.utils.text import truncate_words

from djangosearch.models import Document
from djangosearch.utils import get_summary_length

class SearchEngine(object):
    """
    Abstract search engine base class.
    """

    def get_identifier(self, obj):
        """
        Get an unique identifier for the object.

        If not overridden, uses <app_label>.<object_name>.<pk>.
        """
        return "%s.%s.%s" % (obj._meta.app_label, obj._meta.module_name, obj._get_pk_val())

    def update(self, indexer, iterable):
        raise NotImplementedError

    def remove(self, obj):
        raise NotImplementedError

    def clear(self, models):
        raise NotImplementedError

    def search(self, query, models=None, order_by=["-relevance"], limit=None, offset=None):
        raise NotImplementedError

    def prep_value(self, db_field, value):
        """
        Hook to give the backend a chance to prep an attribute value before
        sending it to the search engine. By default, just force it to unicode.
        """
        return force_unicode(value)
        

class DocumentSearchEngine(SearchEngine):
    """
    A search base class for use with the Document model.
    """
    
    def update(self, indexer, iterable):
        for obj in iterable:
            content_type = ContentType.objects.get_for_model(obj)
            doc, created = Document.objects.get_or_create(
                                content_type=content_type, object_id=obj.pk)
            doc.title = unicode(obj)
            doc.text = indexer.flatten(obj)
            doc.save()
    
    def remove(self, obj):
        content_type = ContentType.objects.get_for_model(obj)
        try:
            Document.objects.get(content_type=content_type,
                                 object_id=obj.pk).delete()
        except Document.DoesNotExist:
            pass
    
    def clear(self, models):
        Document.objects.all().delete()
