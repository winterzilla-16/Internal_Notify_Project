from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.db import transaction

from notify.services.savefile import get_available_filename
from notify.models import Notification, User




# ----- Web App: Login Logic ----- 
@never_cache
def login_view(request):
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )

        if user:
            login(request, user)

            # ✅ เพิ่ม toast ตรงนี้
            if user.is_staff:
                messages.success(request, "เข้าสู่ระบบผู้ดูแลสำเร็จ")
            else:
                messages.success(request, "เข้าสู่ระบบสำเร็จ")

            # ❗ redirect กลับ / ให้ middleware จัดการต่อ
            return redirect('/')

        else:
            messages.error(request, 'Username หรือ Password ไม่ถูกต้อง')
            return redirect('/')

    return render(request, 'login.html')


# ----- Web App: Log Out Logic ----- 
@never_cache
@login_required(login_url='login')
def logout_view(request):
    logout(request)
    messages.warning(request, "ออกจากระบบเรียบร้อยแล้ว")
    return redirect('/')


# ----- Routing Logic  ----- 

# Dashboard
@never_cache
@login_required(login_url='login')
def user_dashboard(request):

    # ----- Admin redirect -----
    if request.user.is_staff:
        return redirect('admin_dashboard')

    # ----- Query notifications ของ user -----
    notifications_qs = (
        Notification.objects
        .filter(user=request.user)
        .order_by("-created_at")   # ใหม่สุดอยู่บน
    )

    # ----- Pagination (5 rows / page) -----
    paginator = Paginator(notifications_qs, 5)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    total_pages = paginator.num_pages if paginator.count > 0 else 0

    # ----- Context -----
    context = {
        "notifications": page_obj,     
        "page_obj": page_obj,
        "total_pages": total_pages,
        "MEDIA_URL": settings.MEDIA_URL,
    }

    return render(request, "dashboard.html", context)

# Dashboard (ADMIN)
@never_cache
@login_required(login_url='login')
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('dashboard')

    # ====== Notifications (real db: notifications + reminders) ======
    notif_qs = (
        Notification.objects
        .select_related('user')
        .order_by('-created_at')
    )

    notif_page_num = request.GET.get('notif_page', 1)
    notif_paginator = Paginator(notif_qs, 5)  # 5 rows data (header แยกใน template)
    notif_page = notif_paginator.get_page(notif_page_num)

    # ====== Users (real db: users) ======
    users_qs = User.objects.order_by('-date_joined')
    user_page_num = request.GET.get('user_page', 1)
    user_paginator = Paginator(users_qs, 5)   # 5 rows data
    user_page = user_paginator.get_page(user_page_num)

    context = {
        "notif_page": notif_page,
        "user_page": user_page,

        # ใช้รักษาหน้าปัจจุบันเวลาคลิก next/prev ของอีกตาราง
        "notif_page_num": notif_page.number if notif_page.paginator.count else 0,
        "notif_page_total": notif_page.paginator.num_pages if notif_page.paginator.count else 0,

        "user_page_num": user_page.number if user_page.paginator.count else 0,
        "user_page_total": user_page.paginator.num_pages if user_page.paginator.count else 0,
    }
    return render(request, "admin/dashboard.html", context)


# Create User Function (ADMIN)
@never_cache
@login_required(login_url='login')
def admin_create_user(request):
    # เช็คสิทธิ์ admin เท่านั้น
    if not request.user.is_staff:
        return redirect('/dashboard/')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        telegram_chat_id = request.POST.get('telegram_chat_id')
        department = request.POST.get("department")
        role = request.POST.get("role", "user")

        if not username or not password:
            messages.error(request, 'กรุณากรอกข้อมูลให้ครบ')
            return redirect('admin_create_user')
        
        if not department:
            messages.error(request, "กรุณาเลือกแผนก (Department)")
            return redirect("admin_create_user")
        
        if role not in ("user", "admin"):
            messages.error(request, "Role ไม่ถูกต้อง")
            return redirect('admin_create_user')

        if role == "user" and not telegram_chat_id:
            messages.error(
                request,
                "บัญชีผู้ใช้งานทั่วไป (User) ต้องระบุ Telegram Chat ID"
            )
            
            return render(request, "admin_create_user", {
                    "departments": User.DEPARTMENT_CHOICES,
                    "form": {
                        "username": username,
                        "telegram_chat_id": telegram_chat_id,
                        "department": department,
                        "role": role,
                    }
                })

            # return redirect('admin_create_user')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username นี้มีอยู่แล้ว')
            return redirect('admin_create_user')

        # สร้าง user ใหม่
        new_user = User.objects.create_user(
            username=username,
            password=password
        )

        # ใส่ telegram_chat_id
        new_user.telegram_chat_id = telegram_chat_id
        new_user.department = department
        new_user.is_staff = (role == "admin")
        new_user.save()

        messages.success(request, "สร้างผู้ใช้งานสำเร็จ")
        return redirect('admin_dashboard')


    return render(request, 'admin/create_user.html', {"departments": User.DEPARTMENT_CHOICES})


# Delete User Function (ADMIN)
@never_cache
@login_required(login_url='login')
def admin_delete_user(request, user_id):
    if not request.user.is_staff:
        return redirect('dashboard')

    # ป้องกันการลบผ่าน GET
    if request.method != "POST":
        return redirect('admin_dashboard')

    target = get_object_or_404(User, id=user_id)

    # แนะนำให้กันลบตัวเอง (ปลอดภัยกว่า)
    if target.id == request.user.id:
        messages.error(request, "ไม่สามารถลบบัญชีของตัวเองได้")
        return redirect('admin_dashboard')

    target.delete()
    messages.success(request, "ลบบัญชีเรียบร้อยแล้ว")
    return redirect('admin_dashboard')


# Edit User (ADMIN)
# =========================
@never_cache
@login_required(login_url='login')
def admin_edit_user(request, user_id):

    # ----- Permission -----
    if not request.user.is_staff:
        return redirect('dashboard')

    target = get_object_or_404(User, id=user_id)

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        telegram_chat_id = request.POST.get("telegram_chat_id", "").strip()
        is_staff = request.POST.get("is_staff") == "on"

        # ===== 1. Username ซ้ำ =====
        if User.objects.filter(username=username).exclude(id=target.id).exists():
            messages.error(request, "ไม่สามารถใช้ Username นี้ได้")
            return render(request, "admin/edit_user.html", {"target": target})

        # ===== 2. Admin พยายามถอดสิทธิ์ตัวเอง =====
        if target.id == request.user.id and not is_staff:
            messages.error(request, "คุณไม่สามารถลบสิทธิ์ของตัวเองได้")
            return render(request, "admin/edit_user.html", {"target": target})

        # ===== 3. Update fields =====
        target.username = username
        target.telegram_chat_id = telegram_chat_id
        target.is_staff = is_staff

        # password (ถ้าไม่กรอก → ใช้ของเดิม)
        if password:
            target.password = make_password(password)

        try:
            target.save()
            messages.success(request, "บันทึกการแก้ไขเรียบร้อยแล้ว")
            return redirect("admin_dashboard")
        except Exception:
            messages.error(request, "ไม่สามารถบันทึกการแก้ไขได้")
            return render(request, "admin/edit_user.html", {"target": target})

    # ===== GET =====
    return render(request, "admin/edit_user.html", {
        "target": target
    })



# Delete Notification (USER)
@never_cache
@login_required(login_url='login')
def delete_notification(request, notification_id):

    # ป้องกันการลบผ่าน GET
    if request.method != "POST":
        return redirect('dashboard')

    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user  # 🔐 ต้องเป็นของ user คนนั้นเท่านั้น
    )

    try:
        notification.delete()
        messages.success(request, "ลบการแจ้งเตือนสำเร็จ ✅")
    except Exception:
        messages.error(request, "ลบการแจ้งเตือนไม่สำเร็จ ❌")

    return redirect('dashboard')


# Create Notification (USER)
@never_cache
@login_required(login_url="login")
def create_notification(request):

    if request.method == "POST":

        # =====================
        # 1. อ่านค่าจากฟอร์ม
        # =====================
        title = request.POST.get("title")
        description = request.POST.get("description")
        event_type = request.POST.get("event_type")

        event_datetime_raw = request.POST.get("event_datetime")
        start_datetime_raw = request.POST.get("start_datetime")

        interval_value = request.POST.get("interval_value") or None
        interval_unit = request.POST.get("interval_unit") or None

        uploaded_file = request.FILES.get("file")

        # =====================
        # 2. แปลง datetime ให้เป็น aware
        # =====================
        event_datetime = None
        start_datetime = None

        if event_datetime_raw:
            event_datetime = timezone.make_aware(
                datetime.strptime(event_datetime_raw, "%Y-%m-%dT%H:%M")
            )

        if start_datetime_raw:
            start_datetime = timezone.make_aware(
                datetime.strptime(start_datetime_raw, "%Y-%m-%dT%H:%M")
            )

        # =====================
        # 3. สร้าง Notification
        # =====================
        notification = Notification.objects.create(
            user=request.user,
            title=title,
            description=description,
            event_type=event_type,
            event_datetime=event_datetime,
            start_datetime=start_datetime,
            interval_value=interval_value,
            interval_unit=interval_unit,
            status="pending",
            retry_count=0,
        )

        # =====================
        # 4. จัดการไฟล์แนบ
        # =====================
        if uploaded_file:
            upload_dir = settings.MEDIA_ROOT
            upload_dir.mkdir(exist_ok=True)

            original_name = uploaded_file.name
            safe_name = get_available_filename(upload_dir, original_name)

            fs = FileSystemStorage(location=upload_dir)
            filename = fs.save(safe_name, uploaded_file)

            notification.file = filename
            notification.save(update_fields=["file"])

        # =====================
        # 6. Feedback + Redirect
        # =====================
        messages.success(request, "สร้างการแจ้งเตือนเรียบร้อยแล้ว")
        return redirect("dashboard")

    # GET
    return render(request, "notifications/create_notification.html")


# Edit Notification (USER)
@never_cache
@login_required(login_url="login")
@transaction.atomic
def edit_notification(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)

    if request.method == "POST":
        # =====================
        # 1) อ่านค่าจากฟอร์ม
        # =====================
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        event_type = request.POST.get("event_type")

        event_datetime_raw = request.POST.get("event_datetime") or None
        start_datetime_raw = request.POST.get("start_datetime") or None
        interval_value = request.POST.get("interval_value") or None
        interval_unit = request.POST.get("interval_unit") or None

        uploaded_file = request.FILES.get("file")

        # =====================
        # 2) Validate ตาม event_type
        # =====================
        if not title:
            messages.error(request, "กรุณากรอก Title")
            return render(request, "notifications/edit_notification.html", {
                "notification": notification,
            })

        if event_type == "one_time":
            if not event_datetime_raw:
                messages.error(request, "กรุณาเลือก Event Datetime (One Time)")
                return render(request, "notifications/edit_notification.html", {
                    "notification": notification,
                })
        elif event_type == "recurring":
            if not (start_datetime_raw and interval_value and interval_unit):
                messages.error(request, "กรุณากรอก Start/Interval ให้ครบ (Recurring)")
                return render(request, "notifications/edit_notification.html", {
                    "notification": notification,
                })
        else:
            messages.error(request, "Event Type ไม่ถูกต้อง")
            return render(request, "notifications/edit_notification.html", {
                "notification": notification,
            })

        # =====================
        # 3) แปลง datetime เป็น aware (Bangkok)
        # =====================
        # NOTE: input datetime-local ไม่มี timezone -> ต้อง make_aware
        from datetime import datetime

        event_datetime = None
        start_datetime = None

        if event_datetime_raw:
            event_datetime = timezone.make_aware(datetime.strptime(event_datetime_raw, "%Y-%m-%dT%H:%M"))

        if start_datetime_raw:
            start_datetime = timezone.make_aware(datetime.strptime(start_datetime_raw, "%Y-%m-%dT%H:%M"))

        # =====================
        # 4) Update Notification (เริ่มรอบใหม่)
        # =====================
        notification.title = title
        notification.description = description
        notification.event_type = event_type

        notification.event_datetime = event_datetime if event_type == "one_time" else None
        notification.start_datetime = start_datetime if event_type == "recurring" else None
        notification.interval_value = int(interval_value) if (event_type == "recurring" and interval_value) else None
        notification.interval_unit = interval_unit if event_type == "recurring" else None

        # เริ่มรอบใหม่ทั้งหมด
        notification.status = "pending"
        notification.retry_count = 0

        # ถ้าคุณมี field last_sent_event_at / last_sent... ให้ reset ด้วย
        if hasattr(notification, "last_sent_event_at"):
            notification.last_sent_event_at = None

        notification.save()

        # =====================
        # 5) ถ้ามีอัปโหลดไฟล์ใหม่ -> ลบไฟล์เก่า + save ใหม่
        # =====================
        if uploaded_file:
            if notification.file:
                old_path = settings.MEDIA_ROOT / notification.file
                if old_path.exists():
                    old_path.unlink(missing_ok=True)

            upload_dir = settings.MEDIA_ROOT / "user_uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)

            safe_name = get_available_filename(str(upload_dir), uploaded_file.name)
            fs = FileSystemStorage(location=upload_dir)
            filename = fs.save(safe_name, uploaded_file)

            # เก็บ path ลง DB (ต้องเป็น relative จาก MEDIA_ROOT)
            notification.file = f"user_uploads/{filename}"
            notification.save(update_fields=["file"])

        messages.success(request, "บันทึกการแก้ไขเรียบร้อยแล้ว ✅")
        return redirect("dashboard")

    return render(request, "notifications/edit_notification.html", {
        "notification": notification,
    })


from pathlib import Path

@never_cache
@login_required(login_url="login")
@transaction.atomic
def remove_notification_file(request, notification_id):
    if request.method != "POST":
        return redirect("dashboard")

    notification = get_object_or_404(
        Notification, id=notification_id, user=request.user
    )

    if not notification.file:
        messages.warning(request, "ไม่พบไฟล์แนบ")
        return redirect("edit_notification", notification_id=notification.id)

    file_path = Path(settings.MEDIA_ROOT) / notification.file

    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            messages.error(request, "ไม่สามารถลบไฟล์ได้")
            print("[FILE] delete error:", e)
            return redirect("edit_notification", notification_id=notification.id)

    notification.file = None
    notification.save(update_fields=["file"])

    messages.success(request, "ลบไฟล์แนบเรียบร้อยแล้ว ✅")
    return redirect("edit_notification", notification_id=notification.id)


# Send Now Notification (USER)
@never_cache
@login_required(login_url='login')
def send_now_notification(request, notification_id):

    # ป้องกันการยิงผ่าน GET
    if request.method != "POST":
        return redirect("dashboard")

    # ดึง notification ของ user คนนั้นเท่านั้น
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )

    try:
        from notify.services.telegram_sender import send_telegram_message

        success = send_telegram_message(notification)

        if success:
            messages.success(
                request,
                "ส่งข้อความทดสอบเรียบร้อยแล้ว ✅"
            )
        else:
            messages.error(
                request,
                "ไม่สามารถส่งข้อความทดสอบได้ ❌"
            )

    except Exception:
        messages.error(
            request,
            "เกิดข้อผิดพลาดระหว่างส่งข้อความ ❌"
        )

    return redirect("dashboard")