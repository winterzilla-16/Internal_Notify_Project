from django.db import models
from django.contrib.auth.models import AbstractUser


# =====================
# User Table
# =====================

class User(AbstractUser):
    """
    Custom User Model for InternalNotify

    - ใช้ Django Auth
    - แยก admin / user ด้วย is_staff
    - telegram_chat_id ไม่ unique
    """

    telegram_chat_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Telegram chat ID for sending notifications"
    )

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.username


# =====================
# Notification Table
# =====================

class Notification(models.Model):
    EVENT_TYPE_CHOICES = [
        ('one_time', 'One Time'),
        ('recurring', 'Recurring'),
    ]

    INTERVAL_UNIT_CHOICES = [
        ('minute', 'minute'),
        ('hour', 'hour'),
        ('day', 'day'),
        ('month', 'month'),
        ('year', 'year'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    title = models.TextField()
    description = models.TextField(null=True, blank=True)

    # เก็บ path / filename ตาม database design
    file = models.TextField(null=True, blank=True)

    event_type = models.CharField(
        max_length=10,
        choices=EVENT_TYPE_CHOICES
    )

    event_datetime = models.DateTimeField(null=True, blank=True)
    start_datetime = models.DateTimeField(null=True, blank=True)

    interval_value = models.IntegerField(null=True, blank=True)
    interval_unit = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=INTERVAL_UNIT_CHOICES
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'

    def __str__(self):
        return self.title


# =====================
# Reminder Table
# =====================

class Reminder(models.Model):
    OFFSET_UNIT_CHOICES = [
        ('minute', 'minute'),
        ('hour', 'hour'),
        ('day', 'day'),
        ('month', 'month'),
    ]

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='reminders',
        db_column='notification_id'
    )

    offset_value = models.IntegerField()
    offset_unit = models.CharField(
        max_length=10,
        choices=OFFSET_UNIT_CHOICES
    )

    class Meta:
        db_table = 'reminders'

    def __str__(self):
        return f'{self.offset_value} {self.offset_unit}'
