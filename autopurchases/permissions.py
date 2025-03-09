from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

from autopurchases.models import Contact, Order, Shop, User


class IsMeOrAdmin(BasePermission):
    message = "Only profile owners can make changes"

    def has_object_permission(self, request: Request, view, obj: User):
        return request.user.is_staff or request.user == obj


class IsManagerOrAdmin(BasePermission):
    message = "Only shop administrators can make changes"

    def has_object_permission(self, request: Request, view, obj: Shop):
        return request.user.is_staff or request.user in obj.managers.all()


class IsManagerOrAdminOrReadOnly(IsManagerOrAdmin):
    def has_object_permission(self, request: Request, view, obj: Shop):
        return (
            super().has_object_permission(request=request, view=view, obj=obj)
            or request.method in SAFE_METHODS
        )


class IsCartOwnerOrAdmin(BasePermission):
    message = "Only cart owners can make changes"

    def has_object_permission(self, request: Request, view, obj: Order):
        return request.user.is_staff or obj.customer == request.user


class IsAdminOrReadOnly(BasePermission):
    message = "Only admins can make changes"

    def has_permission(self, request: Request, view):
        return request.user.is_staff or request.method in SAFE_METHODS
