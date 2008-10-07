from django.db.models import signals
from django.utils.encoding import smart_unicode
from django.template import loader, Context, TemplateDoesNotExist
from djangosearch.query import RELEVANCE

class ModelIndex(object):

    def __init__(self, fields=[], model=None):
        # Avoid a circular import by putting this here
        from djangosearch.backends import backend
        self.fields = fields
        self.model = model
        self.engine = backend.SearchEngine()

    def contribute_to_class(self, model, name):
        self.model = model
        signals.post_save.connect(self.update_object,sender=model)
        signals.post_delete.connect(self.remove_object, sender=model)
        setattr(model, name, ModelIndexDescriptor(self))
        register_indexer(model, self)

    def get_query_set(self):
        """
        Get the default QuerySet to index when doing a full update.
        
        Subclasses can override this method to avoid indexing certain objects.
        """
        return self.model._default_manager.all()

    def flatten(self, obj):
        """
        Flatten an object for indexing.
        
        First, we try to load a template, '{app_name}/{model_name}_index.txt'
        and if found, returns the result of rendering that template. 'object'
        will be in its context.
        
        If the template isn't found, defaults to a newline-joined list of each
        of the object's fields, which may or may not be what you want;
        subclasses which want to influence indexing behavior probably want to
        start here.
        """
        # TODO: not sold on the template path, but this works for now
        opts = obj._meta
        try:
            t = loader.get_template('%s/%s_index.txt' % (opts.app_label, opts.module_name))
            return t.render(Context({'object': obj}))
        except TemplateDoesNotExist:
            #print "template not found: '%s/%s_index.txt'" % (opts.app_label, opts.module_name)
            return "\n".join([smart_unicode(getattr(obj, f.attname)) for f in obj._meta.fields])

    def should_index(self, obj):
        """
        Returns True if the given object should be indexed.
        
        Subclasses that limit indexing using get_query_set() should also
        define this method to prevent incremental indexing of excluded
        objects.
        """
        return True

    def get_indexed_fields(self, obj):
        """
        Get the individually indexed fields for this object; returns a list of
        (fieldname, value) tuples.
        
        Indexed fields can be searched individually (i,e, "name:jacob"). Most
        subclasses won't need to override the default behavior, which uses the
        ``fields`` initializer argument.
        
        Duplicate field names are allowed. For instance you could return
        
            [('f', 'value 1'), ('f', 'value 2')]
        
        The engine itself is responsible for collapsing that to the proper
        representation if needed.
        
        """
        fields = []
        for field in self.fields:
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
                # see http://code.djangoproject.com/ticket/5390 for a possible fix.
                value = ','.join([smart_unicode(o) for o in value.get_query_set()])
            db_field = obj._meta.get_field(field)
            fields.append((field, self.engine.prep_value(db_field, value)))
        return fields

    def update(self):
        """Update the entire index"""
        self.engine.update(self, self.get_query_set())

    def update_object(self, instance, **kwargs):
        """
        Update the index for a single object. Attached to the class's
        post-save hook.
        """
        self.engine.update(self, [instance])

    def remove_object(self, instance, **kwargs):
        """Remove an object from the index. Attached to the class's delete hook."""
        self.engine.remove(instance)

    def clear(self):
        """Clear the entire index"""
        self.engine.clear(models=[self.model])

    def reindex(self):
        """Completely clear the index for this model and rebuild it."""
        self.clear()
        self.update()

    def search(self, q, order_by=RELEVANCE, limit=None, offset=None):
        """Search the index."""
        return self.engine.search(q, models=[self.model], order_by=order_by, limit=limit, offset=offset)

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
