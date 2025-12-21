from dataclasses import dataclass
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from notify.models import Notification, Reminder
from notify.services.telegram_sender import send_telegram_message

MAX_RETRY = 2  # retry เพิ่มอีก 2 รอบ (รวมส่งจริง = 3)


@dataclass
class DueItem:
    notification: Notification
    kind: str  # "reminder" | "event"
    reminder: Reminder | None
    event_at: timezone.datetime
    send_at: timezone.datetime


def _offset_to_timedelta(offset_value: int, offset_unit: str) -> timedelta:
    value = int(offset_value or 0)
    unit = offset_unit

    if unit == "minute":
        return timedelta(minutes=value)
    if unit == "hour":
        return timedelta(hours=value)
    if unit == "day":
        return timedelta(days=value)
    if unit == "month":
        return timedelta(days=30 * value)  # simple
    if unit == "year":
        return timedelta(days=365 * value)

    return timedelta(0)


def get_event_at(n: Notification):
    """
    one_time  -> event_datetime
    recurring -> start_datetime (ใช้เป็น "รอบถัดไป" ของ recurring)
    """
    if n.event_type == "one_time":
        return n.event_datetime
    return n.start_datetime


def build_due_items(now=None) -> list[DueItem]:
    """
    สร้างรายการสิ่งที่ "ถึงเวลาส่ง" จริง ๆ
    (รวม reminders + event หลัก)
    """
    now = now or timezone.now()

    qs = (
        Notification.objects
        .filter(status="pending")
        .select_related("user")
        .prefetch_related("reminders")
        .order_by("-created_at")
    )

    due: list[DueItem] = []

    for n in qs:
        event_at = get_event_at(n)
        if not event_at:
            continue

        # 1) reminders (ส่งก่อน event)
        # ถ้า event หลักในรอบนี้ส่งไปแล้ว -> ไม่ต้องส่ง reminder ย้อนหลัง
        if n.last_sent_event_at != event_at:
            for r in n.reminders.all():
                delta = _offset_to_timedelta(r.offset_value, r.offset_unit)
                send_at = event_at - delta

                if send_at <= now and r.last_sent_event_at != event_at:
                    due.append(DueItem(
                        notification=n,
                        kind="reminder",
                        reminder=r,
                        event_at=event_at,
                        send_at=send_at
                    ))

        # 2) event หลัก (ส่งตรงเวลา event)
        if event_at <= now and n.last_sent_event_at != event_at:
            due.append(DueItem(
                notification=n,
                kind="event",
                reminder=None,
                event_at=event_at,
                send_at=event_at
            ))

    # เรียงให้ reminder มาก่อน event หลัก (เพื่อให้ 10m มาก่อน event)
    due.sort(key=lambda x: (x.notification.id, x.send_at, 0 if x.kind == "reminder" else 1))
    return due


def process_notifications():
    now = timezone.now()
    due_items = build_due_items(now=now)

    print(f"[ENGINE] Found {len(due_items)} due items")
    for item in due_items:
        print(f"[ENGINE] Processing {item.kind} for notification {item.notification.id}")
        process_due_item(item)


@transaction.atomic
def process_due_item(item: DueItem):
    n = item.notification

    try:
        success = send_telegram_message(n)  # ส่ง description + file (ตามที่คุณต้องการ)
        if success:
            handle_success(item)
        else:
            handle_failure(item)

    except Exception:
        handle_failure(item)


def handle_success(item: DueItem):
    n = item.notification

    if item.kind == "reminder" and item.reminder:
        # ✅ mark reminder ว่าส่งแล้วสำหรับ event รอบนี้
        item.reminder.last_sent_event_at = item.event_at
        item.reminder.save(update_fields=["last_sent_event_at"])
        return

    # ===== event หลัก =====
    if n.event_type == "one_time":
        n.status = "success"
        n.last_sent_event_at = item.event_at
        n.retry_count = 0
        n.save(update_fields=["status", "last_sent_event_at", "retry_count"])
        return

    # recurring: ส่ง event หลักสำเร็จ -> schedule รอบถัดไป
    n.last_sent_event_at = item.event_at
    n.retry_count = 0

    schedule_next_run(n)  # อัปเดต start_datetime = รอบถัดไป
    n.status = "pending"

    n.save(update_fields=["last_sent_event_at", "retry_count", "start_datetime", "status"])


def handle_failure(item: DueItem):
    n = item.notification

    # หมายเหตุ: ในเวอร์ชันนี้ "retry_count" จะเป็นของ notification หลักร่วมกัน
    # (ง่ายสุดตามโค้ดเดิมของคุณ)
    if n.retry_count < MAX_RETRY:
        n.retry_count += 1
        n.save(update_fields=["retry_count"])
        return

    # retry ครบ -> failure
    n.status = "failure"
    n.save(update_fields=["status"])


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
