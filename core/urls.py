# core/urls.py

from django.contrib import admin
from django.urls import path
from django.urls import include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", include("assistant.urls")),
    path("admin/", admin.site.urls),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/", include("django.contrib.auth.urls")),
]
