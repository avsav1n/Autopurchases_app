from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

from autopurchases.models import Shop, User


class IsMeOrAdmin(BasePermission):
    message = "Only profile owners can make changes"

    def has_object_permission(self, request: Request, view, obj: User):
        return request.user == obj or request.user.is_staff


class IsManagerOrAdminOrReadOnly(BasePermission):
    message = "Only shop administrators can make changes"

    def has_object_permission(self, request: Request, view, obj: Shop):
        return (
            request.method in SAFE_METHODS
            or request.user in obj.managers.all()
            or request.user.is_staff
        )
