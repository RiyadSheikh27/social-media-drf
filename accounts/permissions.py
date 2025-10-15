from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    """
    Allow access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class IsModerator(permissions.BasePermission):
    """
    Allow access only to moderators.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'moderator'


class IsUser(permissions.BasePermission):
    """
    Allow access only to regular users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'user'


class IsAdminOrModerator(permissions.BasePermission):
    """
    Allow access to both admin and moderator roles.
    """
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            request.user.role in ['admin', 'moderator']
        )

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of a profile to edit it.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.user == request.user