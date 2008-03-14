tests = """
Tests applicable to all search engines.

>>> from datetime import datetime
>>> a = Article(title='test', date=datetime(2007, 10, 31))

>>> print Article.index.flatten(a)
None
test
2007-10-31 00:00:00

>>> Article.index.get_indexed_fields(a)
[('title', 'test'), ('date', datetime.datetime(2007, 10, 31, 0, 0))]

"""

from django.conf import settings
from django.db import models
from djangosearch import ModelIndex


class Article(models.Model):
    title = models.CharField(max_length=255)
    date = models.DateField()

    index = ModelIndex(fields=['title', 'date'])

    def __unicode__(self):
        return self.title

class Event(models.Model):
    title = models.CharField(max_length=255)
    date = models.DateField()
    is_outdoors = models.BooleanField()

    index = ModelIndex(fields=['title', 'date', 'is_outdoors'])

    def __unicode__(self):
        return self.title

# Load the backend specific tests
if settings.SEARCH_ENGINE == 'estraier':
    from djangosearch.tests import estraier as backend_tests
elif settings.SEARCH_ENGINE == 'solr':
    from djangosearch.tests import solr as backend_tests
else:
    backend_tests = None

__test__ = {'API_TESTS': tests}

if backend_tests:
    __test__['BACKEND_TESTS'] = backend_tests
