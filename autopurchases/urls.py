"""
URL configuration for main project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from autopurchases.views import (
    CartViewSet,
    CeleryTaskView,
    DownloadFileView,
    EmailObtainAuthToken,
    OrderView,
    ShopViewSet,
    StockView,
    UserViewSet,
)

router = DefaultRouter()
router.register("user", UserViewSet, basename="user")
router.register("shop", ShopViewSet, basename="shop")
router.register("cart", CartViewSet, basename="cart")

app_name = "autopurchases"
urlpatterns = [
    path("", include(router.urls)),
    path("order/", OrderView.as_view(), name="order"),
    path("stock/", StockView.as_view(), name="stock"),
    path("task/<str:task_id>/", CeleryTaskView.as_view(), name="celery-result"),
    path("download/<str:task_id>/", DownloadFileView.as_view(), name="download-file"),
    path("login/", EmailObtainAuthToken.as_view(), name="login"),
]
