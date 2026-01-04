from django.shortcuts import redirect
from django.urls import reverse


class AuthFlowMiddleware:
    """
    คุม flow การเข้าเว็บ:
    - login แล้ว ห้ามกลับไปหน้า login
    - ยังไม่ login ห้ามเข้า dashboard / admin
    - คุมสิทธิ์ admin / user
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # หน้า public (เข้าได้โดยไม่ login)
        self.public_paths = [
            '/',
        ]

        # admin pages (custom admin ของคุณ ไม่ใช่ django admin)
        self.admin_paths = [
            'admin_dashboard',
            '/admin-create_user/',
        ]

        # user-only pages (admin ห้ามเข้า)
        self.user_only_paths = [
            '/dashboard/',
            '/notifications/',
            '/notifications/create/',
            '/notifications/edit/',
        ]


    def __call__(self, request):
        path = request.path

        # ข้าม static / django admin
        if path.startswith('/static/') or path.startswith('/admin/'):
            return self.get_response(request)

        # ===============================
        # LOGIN แล้ว
        # ===============================
        if request.user.is_authenticated:

            # login แล้วห้ามกลับหน้า login
            if path in self.public_paths:
                if request.user.is_staff:
                    return redirect('admin_dashboard')
                return redirect('/dashboard/')

            # user-only pages (admin ห้ามเข้า)
            if any(path.startswith(p) for p in self.user_only_paths):
                if request.user.is_staff:
                    return redirect('admin_dashboard')

            # admin-only pages (user ห้ามเข้า)
            if any(path.startswith(p) for p in self.admin_paths):
                if not request.user.is_staff:
                    return redirect('/dashboard/')



        # ===============================
        # ยังไม่ LOGIN
        # ===============================
        else:
            protected_paths = self.admin_paths + [self.user_only_paths]

            if path in protected_paths:
                return redirect('/')

        return self.get_response(request)
