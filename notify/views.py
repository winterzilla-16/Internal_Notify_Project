from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from django.conf import settings
from .models import Notification, User, Reminder


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
    if request.user.is_staff:
        return redirect('admin_dashboard')
    return render(request, 'dashboard.html')

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
        .prefetch_related('reminders')
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
        is_staff = request.POST.get('is_staff')  # checkbox

        if not username or not password:
            messages.error(request, 'กรุณากรอกข้อมูลให้ครบ')
            return redirect('admin_create_user')

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

        # กำหนดสิทธิ์ admin หรือ user
        if is_staff == 'on':
            new_user.is_staff = True

        new_user.save()

        messages.success(request, "สร้างผู้ใช้งานสำเร็จ")
        return redirect('admin_dashboard')


    return render(request, 'admin/create_user.html')


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

        event_datetime = request.POST.get("event_datetime") or None
        start_datetime = request.POST.get("start_datetime") or None
        interval_value = request.POST.get("interval_value") or None
        interval_unit = request.POST.get("interval_unit") or None

        uploaded_file = request.FILES.get("file")

        # =====================
        # 2. สร้าง Notification
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
            status="pending",  # สำคัญมาก
        )

        # =====================
        # 3. จัดการไฟล์แนบ
        # =====================
        if uploaded_file:
            file_path = f"{notification.id}_{uploaded_file.name}"
            full_path = settings.MEDIA_ROOT / file_path

            with open(full_path, "wb+") as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            # เก็บ path ลง DB
            notification.file = file_path
            notification.save()

        # =====================
        # 4. สร้าง Reminders (หลายรายการ)
        # =====================
        offset_values = request.POST.getlist("offset_value[]")
        offset_units = request.POST.getlist("offset_unit[]")

        for val, unit in zip(offset_values, offset_units):
            Reminder.objects.create(
                notification=notification,
                offset_value=int(val),
                offset_unit=unit
            )

        # =====================
        # 5. Feedback + Redirect
        # =====================
        messages.success(request, "สร้างการแจ้งเตือนเรียบร้อยแล้ว")
        return redirect("dashboard")

    # GET
    return render(request, "notifications/create_notification.html")