from django.contrib import admin
from .models import Contact, Conversation, Message

class MessageInline(admin.TabularInline):
    model = Message
    extra = 0  # how many rows to show

class ConversationAdmin(admin.ModelAdmin):
    inlines = [
        MessageInline,
    ]

admin.site.register(Contact)
admin.site.register(Conversation, ConversationAdmin)
admin.site.register(Message)
