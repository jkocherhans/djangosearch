============
djangosearch
============

``djangosearch`` provides an interface for searching Django models using 
various full text search methods.

Overview
========

There are two types of backend supported by djangosearch. By default, the built
in full text search functionality of the database engine will be used, which is 
currently limited to MySQL and PostgreSQL. Optionally, a database independent 
search engine can be used such as Solr, Sphinx or Xapian. 

Let's take this model as an example:

    from django.db import models
    import djangosearch

    class Event(models.Model):
        title = models.CharField(max_length=255)
        date = models.DateField()
        is_outdoors = models.BooleanField()

        index = djangosearch.ModelIndex(text=['title'], 
                                        additional=['date', 'is_outdoors'])
    
Assuming this is in ``mysite/events/models.py``, we can perform a search on 
its index:

    from mysite.events.models import Event
    results = Event.index.search("django conference")
    
    for result in results:
        print "%s (%s)" % (result, result._relevance)
    
If you are using the full text features built into your database engine, 
``results`` simply contains a ``QuerySet``, ordered by relevance by default. 
Otherwise, a ``SearchResults`` object is returned, which acts very similarly to 
a queryset.

Backends
========

By default, djangosearch attempts to use the full text search features of the 
database backend. This currently requires a minimum of either MySQL 4.0.1 or 
PostgreSQL 8.3.

If you do not use MySQL or PostgreSQL, or simply wish to use another search 
engine, there are a number of other backends available. You can specify the one 
to use with the ``SEARCH_ENGINE`` setting.

``solr``
--------

``solr`` provides an interface for Apache's Solr_ search engine. It depends on 
pysolr_ and requires a ``SOLR_URL`` setting for specifying the URL of your Solr 
server.

Take these ``settings.py`` lines for example:

    SEARCH_ENGINE = "solr"
    SOLR_URL = "http://localhost:8080/solr/default/"

.. _Solr: http://lucene.apache.org/solr/
.. _pysolr: http://code.google.com/p/pysolr/

Indexing a model
================

A search index can be added to a model by using the ``djangosearch.ModelIndex`` 
manager. ``ModelIndex`` takes two arguments; ``text`` and ``additional``.

``text``
    The ``text`` argument lets you specify the fields on the model that will be
    used for the main full text index.
    
    When not using the database engine's full text search, a template can be 
    used to represent the model. If the template 
    ``<app_label>/<model_name>_index.txt`` exists, the ``text`` argument will be
    ignored, and the output of that template will be used instead.
    
``additional``
    A list of additional fields can be provided which are indexed, but not 
    included in the main index. They can be searched with the ``field:keyword``
    syntax.
    
    The behaviour of this is likely to change when there is support for
    indexing data which isn't text.
    
The manager has one method of interest:

``search(query)``
~~~~~~~~~~~~~~~~~

This searches the model's for ``query`` (in the `Query format`_ specified 
below) and returns either a ``QuerySet`` or a ``SearchResults`` object depending
on whether it searches using the database engine or not (see `Handling results`_ 
below).

Query format
============

A common query format is used regardless of what backend you have chosen. By 
default, the documents matching all the expressions are matched, unless 
overridden by ``or``.

Operators
---------

``expression or expression``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Matches documents matched by either of the expressions.

It must be enclosed in brackets if you are using more than two expressions in 
the query, but this is a subtle quirk in the parser so will likely change.

``-expression``
~~~~~~~~~~~~~~~

Matches documents which don't match the expression.

Bracketed expressions
---------------------

Expressions can be grouped with brackets to create sub expressions. This is 
useful for controlling boolean expressions. For example:

    (python or perl) web framework

Quoted phrases
--------------

A phrase contained in double quotes ("") matches documents containing that 
exact phrase.

Searching within an additional field
------------------------------------

The ``field:keyword`` syntax can be used to search within the additional fields
specified when the index was created. Currently, only single words can be used 
in each expression.

Handling results
================

If you are using your database engine's full text functionality, ``search()`` 
will simply return a ``QuerySet``. See the `database API documentation`_ for
details on how to manipulate and access the results.

However, if you are not using a database engine backend, a ``SearchResults`` 
object will be returned. ``SearchResults`` acts very similarly to a 
``QuerySet``; they can be chained and the results are loaded lazily.

Again in the same way as ``QuerySet``, ``SearchResults`` can be sliced:

    search("query")[5:10]

Individual results can also be fetched:

    search("query")[0]
    
For results contained in both ``SearchResults`` or a ``QuerySet``, each object 
is given a ``_relevance`` attribute, which is a float indicating the 
relevance of the result (higher is more relevant).

.. _database API documentation: http://www.djangoproject.com/documentation/db-api/

SearchResults methods that return new SearchResults
---------------------------------------------------

``all()``
~~~~~~~~~

Returns a copy of the current ``SearchResults`` object.

SearchResults methods that do not return SearchResults
------------------------------------------------------

``count()``
~~~~~~~~~~~

Returns an integer representing the number of results.

``count()`` will always use the most efficient method of fetching the number
of results, so this should always be used rather than calling ``len()``.

``raw()``
~~~~~~~~~

To avoid loading all the results from the database, this method returns the data
received from the search engine as a list of dictionaries with ``model``, ``pk``
and ``relevance`` keys. ``pk`` is the integer primary key of the object,
``model`` is the model containing the primary key and ``relevance`` is a float
representing the relevance of the result.

Searching all indexed models
============================

``djangosearch.search(query, models=None)`` 
-------------------------------------------

Supplied with a query (in the `Query format`_ specified above), returns the
documents that match the query in all the indexed models. Optionally, a list of
models to limit the search to can be provided with the ``models`` argument.

This only works when you are not using a database engine's full text 
features.

Searching multiple models with the database engine
--------------------------------------------------

If you are using a database engine for full text search, you can create a model 
to contain all the objects and use the hook signals to update it. To be 
continued....
