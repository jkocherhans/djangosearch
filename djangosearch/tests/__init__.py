tests = """
Tests applicable to all search engines.

>>> from datetime import datetime
>>> a = Article(title='test', date=datetime(2007, 10, 31))

>>> print Article.index.flatten(a)
test

# FIXME: these might not necessarily be constant across backends thanks to 
# prep_value
>>> Article.index.get_additional_values(a)
{'date': u'2007-10-31 00:00:00'}

>>> print Article.index.get_text_values(a)
{'title': u'test'}

"""

# TODO: dummy backend tests

from django.conf import settings
from django.db import models
import djangosearch


class Article(models.Model):
    title = models.CharField(max_length=255)
    date = models.DateField()

    index = djangosearch.ModelIndex(text=['title'], additional=['date'])

    def __unicode__(self):
        return self.title

class Event(models.Model):
    title = models.CharField(max_length=255)
    date = models.DateField()
    is_outdoors = models.BooleanField()

    index = djangosearch.ModelIndex(text=['title'], 
                                    additional=['date', 'is_outdoors'])
    
    def __unicode__(self):
        return self.title

# Load the backend specific tests
backends = ['mysql', 'postgresql', 'solr']

if settings.SEARCH_ENGINE in backends:
    backend_tests = __import__('djangosearch.tests.%s' % settings.SEARCH_ENGINE, 
            {}, {}, [''])
else:
    backend_tests = None

__test__ = {'API_TESTS': tests}

if backend_tests:
    __test__['BACKEND_TESTS'] = backend_tests
