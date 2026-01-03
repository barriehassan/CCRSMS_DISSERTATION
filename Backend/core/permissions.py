from rest_framework.permissions import BasePermission


class IsCitizen(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.user_type == "CITIZEN")


class IsOwnerCitizen(BasePermission):
    def has_object_permission(self, request, view, obj):
        return bool(request.user.user_type == "CITIZEN" and obj.citizen_id == request.user.id)


class CitizenCanEditOnlyWhenSubmitted(BasePermission):
    """
    Citizens can UPDATE/DELETE only when complaint.status == "SUBMITTED".
    Read-only (GET/list) is always allowed for owner.
    """
    allowed_edit_statuses = {"SUBMITTED"}

    def has_object_permission(self, request, view, obj):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True

        # PUT/PATCH/DELETE
        return obj.status in self.allowed_edit_statuses

