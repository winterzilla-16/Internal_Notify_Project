from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),                 # กำหนดเป็นหน้า index (/)
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.user_dashboard, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-create_user/', views.admin_create_user, name='admin_create_user'),
    path("admin/edit-user/<int:user_id>/", views.admin_edit_user, name="admin_edit_user"),
    path('admin/users/<int:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),
    path('notifications/create/', views.create_notification, name='create_notification'),
    path('notifications/delete/<int:notification_id>/', views.delete_notification, name='delete_notification'),
    path('notifications/send-now/<int:notification_id>/', views.send_now_notification, name='send_now_notification'),
    path("notifications/<int:notification_id>/edit/", views.edit_notification, name="edit_notification"),
    path("notifications/<int:notification_id>/remove-file/", views.remove_notification_file, name="remove_notification_file"),
]