from rest_framework.permissions import BasePermission

class IsAdminOrOwner(BasePermission):
    """
    Allows access only to admin users or the owner of the object.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True

        return obj.owner == request.user