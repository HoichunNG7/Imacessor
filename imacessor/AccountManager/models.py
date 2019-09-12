from django.db import models

# Create your models here.
from django.utils import timezone


class Message(models.Model):  # 留言模型
    title = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title
