from django.db import models
from accounts.models import CustomUser

class Contact(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)

    def __str__(self):
        return self.name

class Conversation(models.Model):
    title = models.CharField(max_length=255)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.title

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    question = models.TextField()
    answer = models.TextField()
    context = models.TextField()

    def __str__(self):
        return self.question

class ProductSnapshot(models.Model):
    batch_id = models.CharField(max_length=255, null=True, blank=True)  # A unique ID for this batch of updates
    sku = models.CharField(max_length=255)
    title = models.CharField(max_length=255, null=True, blank=True)
    product_type = models.CharField(max_length=255, null=True, blank=True)
    vendor = models.CharField(max_length=255, null=True, blank=True)
    tags = models.TextField(null=True, blank=True)
    body_html = models.TextField(null=True, blank=True)
    price = models.CharField(max_length=50, null=True, blank=True)
    compare_at_price = models.CharField(max_length=50, null=True, blank=True)
    cost = models.CharField(max_length=50, null=True, blank=True)
    available = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reverted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sku} snapshot in batch {self.batch_id}"