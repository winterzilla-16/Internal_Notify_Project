from dataclasses import dataclass
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from notify.models import Notification
from notify.services.telegram_sender import send_telegram_message

MAX_RETRY = 2  # retry เพิ่มอีก 2 รอบ (รวมส่งจริง = 3)


@dataclass
class DueItem:
    notification: Notification
    event_at: timezone.datetime
    send_at: timezone.datetime


def get_event_at(n: Notification):
    """
    one_time  -> event_datetime
    recurring -> start_datetime (ใช้เป็นรอบปัจจุบัน)
    """
    if n.event_type == "one_time":
        return n.event_datetime
    return n.start_datetime


def build_due_items(now=None) -> list[DueItem]:
    """
    สร้างรายการ notification ที่ถึงเวลาส่ง
    """
    now = now or timezone.now()

    qs = (
        Notification.objects
        .filter(status="pending")
        .select_related("user")
        .order_by("-created_at")
    )

    due: list[DueItem] = []

    for n in qs:
        event_at = get_event_at(n)
        if not event_at:
            continue

        # ส่งเฉพาะรอบที่ยังไม่เคยส่ง
        if event_at <= now and n.last_sent_event_at != event_at:
            due.append(DueItem(
                notification=n,
                event_at=event_at,
                send_at=event_at
            ))

    return due


def process_notifications():
    now = timezone.now()
    due_items = build_due_items(now=now)

    print(f"[ENGINE] Found {len(due_items)} due notifications")

    for item in due_items:
        print(f"[ENGINE] Processing notification {item.notification.id}")
        process_due_item(item)


@transaction.atomic
def process_due_item(item: DueItem):
    n = item.notification

    try:
        success = send_telegram_message(n)
        if success:
            handle_success(item)
        else:
            handle_failure(n)

    except Exception:
        handle_failure(n)


def handle_success(item: DueItem):
    n = item.notification

    # ===== one_time =====
    if n.event_type == "one_time":
        n.status = "success"
        n.last_sent_event_at = item.event_at
        n.retry_count = 0
        n.save(update_fields=[
            "status",
            "last_sent_event_at",
            "retry_count",
        ])
        return

    # ===== recurring =====
    n.last_sent_event_at = item.event_at
    n.retry_count = 0

    schedule_next_run(n)
    n.status = "pending"

    n.save(update_fields=[
        "last_sent_event_at",
        "retry_count",
        "start_datetime",
        "status",
    ])


def handle_failure(notification: Notification):
    if notification.retry_count < MAX_RETRY:
        notification.retry_count += 1
        notification.save(update_fields=["retry_count"])
        return

    notification.status = "failure"
    notification.save(update_fields=["status"])


def schedule_next_run(notification: Notification):
    unit = notification.interval_unit
    value = notification.interval_value or 1

    delta_map = {
        "minute": timedelta(minutes=value),
        "hour": timedelta(hours=value),
        "day": timedelta(days=value),
        "month": timedelta(days=30 * value),   # simple
        "year": timedelta(days=365 * value),
    }

    delta = delta_map.get(unit)
    if not delta:
        return

    notification.start_datetime = timezone.now() + delta
