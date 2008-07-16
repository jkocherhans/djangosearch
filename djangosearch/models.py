from django.db import models
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

class Document(models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    object = generic.GenericForeignKey()
    title = models.CharField(blank=True, null=True, max_length=255)
    text = models.TextField()

    def __unicode__(self):
        if self.title:
            return self.title
        #elif self.object:
        #    return unicode(self.object)
        else:
            return u'Document'