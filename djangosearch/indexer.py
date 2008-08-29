from django.core.exceptions import ImproperlyConfigured
from django.db.models import signals
from django.template import loader, Context, TemplateDoesNotExist
from django.utils.encoding import smart_unicode, force_unicode

class ModelIndex(object):
    """
    A search index for a model. Provides an interface for indexing and 
    searching that model.
    
    When updating the index, the indexer will attempt to the load the template
    ``<app_label>/<model_name>_index.txt``, and if found it will use that as
    the text for the index. Otherwise, the fields specified by ``text`` will be
    used, separated by new lines. For SQL backends, the template will have no
    effect; the fields specified by the ``text`` argument will always be used.
    
    Arguments:
        ``text``
            A list of fields to use as the full text index. This is not
            required if an index template exists.
        
        ``additional``
            A list of additional fields to be indexed. The "field:keyword"
            query syntax can be used to search these. They can also be used
            for sorting and filtering.
            
        ``model``
            The model that is used for searching and indexing. This is not 
            required if this is being used as a manager.
    """
    def __init__(self, text=None, additional=[], model=None):
        self.text = text
        self.additional = additional
        self.model = model
        
        # Avoid a circular import by putting this here
        from djangosearch.backends import backend
        self.backend = backend
        try:
            self.engine = backend.SearchEngine()
        except AttributeError:
            self.engine = None

    def contribute_to_class(self, model, name):
        self.model = model
        signals.post_save.connect(self.update_object, sender=model)
        signals.post_delete.connect(self.remove_object, sender=model)
        setattr(model, name, ModelIndexDescriptor(self))
        register_indexer(model, self)

    def get_query_set(self):
        """
        Get the default QuerySet to use for searches. For non-SQL backends, 
        this will be the QuerySet used for indexing.
        
        Subclasses can override this method to exclude certain objects.
        """
        return self.model._default_manager.all()

    def flatten(self, obj):
        """
        Flatten an object for indexing.

        First, we try to load a template, ``<app_label>/<model_name>_index.txt``
        and if found, returns the result of rendering that template. ``obj``
        will be in its context.

        If the template isn't found, defaults to a newline-joined list of each
        of the fields specified in the ``text`` attribute.
        """
        opts = obj._meta
        try:
            t = loader.get_template('%s/%s_index.txt' 
                    % (opts.app_label, opts.module_name))
            return t.render(Context({'object': obj}))
        except TemplateDoesNotExist:
            if self.text is None:
                raise ImproperlyConfigured("Neither a template nor a text "
                                           "initialization argument has been "
                                           "provided for this index.")
            return "\n".join([smart_unicode(f) 
                              for f in self.get_text_values(obj).values()])

    def should_index(self, obj):
        """
        Returns True if the given object should be indexed. This has no effect
        for SQL backends.
        
        Subclasses that limit indexing using get_query_set() should also
        define this method to prevent incremental indexing of excluded
        objects.
        """
        return True
    
    def get_additional_values(self, obj):
        """
        Get the values for the additionally indexed fields for this object; 
        returns a dictionary mapping field names to values.

        Additional fields can be searched individually (i,e, "name:jacob"). Most
        subclasses won't need to override the default behavior, which uses the
        ``fields`` initializer argument.
        """
        return self._get_field_values(obj, self.additional)
    
    def get_text_values(self, obj):
        """
        Gets the values for the fields that are part of the fulltext index, as 
        specified by the ``text`` intializer argument. Returns a dictionary 
        mapping field names to values.
        """
        return self._get_field_values(obj, self.text)
    
    def _get_field_values(self, obj, fields):
        fields_values = {}
        for field in fields:
            try:
                value = getattr(obj, field)
            except AttributeError:
                continue
            if callable(value):
                value = value()
            elif hasattr(value, 'get_query_set'):
                # default handling for ManyToManyField
                # XXX: note that this is kinda damaged right now because the
                # post_save signal is sent *before* m2m fields are updated.
                # see http://code.djangoproject.com/ticket/5390 for a possible 
                # fix.
                value = ','.join([smart_unicode(o) 
                                  for o in value.get_query_set()])
            db_field = obj._meta.get_field(field)
            if self.engine:
                value = self.engine.prep_value(db_field, value)
            else:
                value = force_unicode(value)
            fields_values[field] = value
        return fields_values
    
    def get_all_fields(self):
        """
        Returns a list of the fields specified by both ``text`` and 
        ``additional``.
        """
        return self.text + self.additional
    
    def update(self):
        """Update the entire index."""
        if self.engine:
            self.engine.update(self, self.get_query_set())

    def update_object(self, instance, **kwargs):
        """
        Update the index for a single object. Attached to the class's
        post-save hook.
        """
        if self.engine:
            self.engine.update(self, [instance])

    def remove_object(self, instance, **kwargs):
        """
        Remove an object from the index. Attached to the class's delete 
        hook.
        """
        if self.engine:
            self.engine.remove(instance)

    def clear(self):
        """Clear the entire index."""
        if self.engine:
            self.engine.clear(models=[self.model])

    def reindex(self):
        """Completely clear the index for this model and rebuild it."""
        self.clear()
        self.update()

    def search(self, query):
        """Search the index."""
        return self.backend.search(query, models=[self.model])

class ModelIndexDescriptor(object):
    # This class ensures indexes aren't accessible via model instances.
    # For example, Poll.index works, but poll_obj.index raises AttributeError.
    def __init__(self, index):
        self.searchindex = index

    def __get__(self, instance, type=None):
        if instance != None:
            raise AttributeError("ModelIndex isn't accessible via %s instances" % type.__name__)
        return self.searchindex

_model_indexers = {}
def register_indexer(model, indexer):
    """Register an model indexer."""
    global _model_indexers
    _model_indexers[model] = indexer

def get_indexer(model):
    """Return a model indexer for a model."""
    return _model_indexers[model]

def get_indexers():
    """Return a dict of model indexers keyed my model."""
    return _model_indexers

def get_indexed_models():
    """Return a list of all models that have registered indexers."""
    return _model_indexers.keys()

def unregister_indexer(model):
    """Remove a registered model indexer"""
    del _model_indexers[model]
