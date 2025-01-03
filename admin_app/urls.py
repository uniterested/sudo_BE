from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.admin_login, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('generate-qr/', views.generate_qr, name='generate_qr'),
    path('download-qr-pdf/', views.download_qr_pdf, name='download_qr_pdf'),
    path('register-user/', views.register_user, name='register_user'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('logout/', views.admin_logout, name='logout'),
    path('send-notification/<str:user_id>/', views.send_notification, name='send_notification'),
]
