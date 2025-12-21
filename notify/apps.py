# notify/apps.py
from django.apps import AppConfig
import os

class NotifyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notify'

    def ready(self):
        # ป้องกัน run ซ้ำตอน autoreload
        if os.environ.get("RUN_MAIN") != "true":
            return

        from notify.scheduler import start
        start()
