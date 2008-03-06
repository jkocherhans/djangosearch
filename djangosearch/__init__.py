"""
Object search engine for Django
"""

from djangosearch.query import RELEVANCE
from djangosearch.indexer import ModelIndex

__all__ = ['search', 'ModelIndex']


def search(query, models=None, order_by=RELEVANCE, limit=25, offset=0):
    """
    Perform a search against the index.
    
    Arguments:
    
        ``query``
            The query string, in common query format.
            
            This is the only required argument.
            
        ``models``
            A list of models (or "app_label.module_name" strings); if given
            only objects of this type will be returned.
            
        ``order_by``
            The field to order the search results by. This field, obviously,
            must be one of the indexed fields on objects to be searched (and
            thus doesn't make much sense unless ``models`` is also given or
            you've got a certain field in common). Defaults to the constant
            ``search.RELEVANCE``, which orders by the engine's
            concept of relevance (whatever that happens to mean :)
            
            Like the database API, you can prefix this field with a ``"-"`` (a
            hyphen) to sort in reverse order.
            
        ``limit``
        ``offset``
            Limit/offset the search results, just like a ``LIMIT X OFFSET Y``
            SQL clause. This may be used to implement pagination.
            
    Note that the performance of the optional parameters is not guarenteed;
    that is, any of the ordering/limiting parameters may be emulated by the
    backend if it doesn't natively support the feature.
    """
    # Delay import of the backend so we have a chance to configure things
    # after importing search, but before we use it.
    from djangosearch.backends import backend
    return backend.SearchEngine().search(query, models, order_by, limit, offset)
