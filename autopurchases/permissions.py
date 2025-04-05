from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

from autopurchases.models import Order, Shop, User


class IsMeOrAdminOrReadOnly(BasePermission):
    message = _("Only profile owners can make changes")

    def has_object_permission(self, request: Request, view, obj: User):
        return request.method in SAFE_METHODS or request.user.is_staff or request.user == obj


class IsManagerOrAdmin(BasePermission):
    message = _("Only shop managers can make changes")

    def has_object_permission(self, request: Request, view, obj: Shop):
        return request.user.is_staff or request.user in obj.managers.all()


class IsManagerOrAdminOrReadOnly(IsManagerOrAdmin):
    def has_object_permission(self, request: Request, view, obj: Shop):
        return request.method in SAFE_METHODS or super().has_object_permission(
            request=request, view=view, obj=obj
        )


class IsCartOwnerOrAdmin(BasePermission):
    message = _("Only cart owners can make changes")

    def has_object_permission(self, request: Request, view, obj: Order):
        return request.user.is_staff or obj.customer == request.user
