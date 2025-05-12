from . import views
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import CustomPasswordResetView


urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name="logout"),

    path('verify_email/<str:token>/', views.verify_email, name='verify_email'),


    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),

    # Other password reset URLs
    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset_sent/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password_reset_complete/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

]
