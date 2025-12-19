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

        # user dashboard
        self.user_dashboard = '/dashboard/'

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

            # user ธรรมดา ห้ามเข้า admin
            if path in self.admin_paths and not request.user.is_staff:
                return redirect('/dashboard/')

            # admin เข้า user dashboard → พาไป admin dashboard
            if path == self.user_dashboard and request.user.is_staff:
                return redirect('admin_dashboard')

        # ===============================
        # ยังไม่ LOGIN
        # ===============================
        else:
            protected_paths = self.admin_paths + [self.user_dashboard]

            if path in protected_paths:
                return redirect('/')

        return self.get_response(request)
