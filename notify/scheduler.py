# notify/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings
from notify.services.notification_engine import process_notifications

scheduler = None

def start():
    global scheduler

    if scheduler:
        return  # กัน start ซ้ำ

    scheduler = BackgroundScheduler(
        timezone=settings.TIME_ZONE
    )

    scheduler.add_job(
        process_notifications,
        trigger='interval',
        seconds=30,  # ตรวจทุก 30 วิ
        id='notification_engine',
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    print("✅ Notification scheduler started")
