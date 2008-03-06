tests = """
Tests applicable to all search engines.

>>> from datetime import date

>>> Event.index.clear()

>>> e1 = Event(title='Halloween Party', date=date(2007, 10, 31), is_outdoors=True)
>>> e1.save()

>>> e2 = Event(title='Christmas Party', date=date(2007, 12, 25), is_outdoors=False)
>>> e2.save()

>>> results = Event.index.search('halloween')
>>> for result in results:
...     print result.object
Halloween Party

>>> results = Event.index.search('christmas')
>>> for result in results:
...     print result.object
Christmas Party


We can do boolean searches on specific fields.

>>> for result in Event.index.search('party', attrs={'is_outdoors': True}):
...     print result.object
Halloween Party

>>> for result in Event.index.search('party', attrs={'is_outdoors': False}):
...     print result.object
Christmas Party


We can order search results by field values instead of relevence. We can only
order by a single field though.

>>> for result in Event.index.search('party', order_by='title'):
...     print result.object
Christmas Party
Halloween Party

>>> for result in Event.index.search('party', order_by='-title'):
...     print result.object
Halloween Party
Christmas Party

>>> results = Event.index.search('party', order_by='date')
>>> for result in results:
...     print result.object
Halloween Party
Christmas Party

>>> results = Event.index.search('party', order_by='-date')
>>> for result in results:
...     print result.object
Christmas Party
Halloween Party


There is also a global search function that we can use to search multiple
models at the same time. It takes the same arguments as the model specific
search methods.

>>> results = search.search('party', order_by='date')
>>> for result in results:
...     print result.object
Halloween Party
Christmas Party

"""

from django.conf import settings
from django.db import models
import search


class Article(models.Model):
    title = models.CharField(max_length=255)
    date = models.DateField()

    index = search.ModelIndex(fields=['title', 'date'])

    def __unicode__(self):
        return self.title

class Event(models.Model):
    title = models.CharField(max_length=255)
    date = models.DateField()
    is_outdoors = models.BooleanField()

    index = search.ModelIndex(fields=['title', 'date', 'is_outdoors'])

    def __unicode__(self):
        return self.title

# Load the backend specific tests
if settings.SEARCH_ENGINE == 'estraier':
    from search.tests import estraier as backend_tests
elif settings.SEARCH_ENGINE == 'solr':
    from search.tests import solr as backend_tests
else:
    backend_tests = None

__test__ = {'API_TESTS': tests}

if backend_tests:
    __test__['BACKEND_TESTS'] = backend_tests
