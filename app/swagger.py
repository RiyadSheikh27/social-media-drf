from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


# 🔐 Define security scheme for JWT Bearer token
security_definitions = {
    'Bearer': {
        'type': 'apiKey',
        'name': 'Authorization',
        'in': 'header',
        'description': (
            "JWT Authorization header using the Bearer scheme.\n\n"
            "Example: **Authorization: Bearer &lt;your_token&gt;**"
        ),
    }
}

# 🧩 Schema configuration for Swagger and Redoc
schema_view = get_schema_view(
    openapi.Info(
        title="Social Media API",
        default_version='v1',
        description=(
            "Comprehensive API documentation for the Social Media Platform.\n\n"
            "This documentation covers all endpoints from both **authentication** "
            "and **global** apps.\n\n"
            "Use the **Authorize** button above to authenticate with your JWT token."
        ),
        terms_of_service="https://yourdomain.com/terms/",
        contact=openapi.Contact(email="support@yourdomain.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=[],
)

schema_view.security_definitions = security_definitions
