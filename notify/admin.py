from django.contrib import admin
from .models import User, Notification, Reminder

admin.site.register(User)
admin.site.register(Notification)
admin.site.register(Reminder)