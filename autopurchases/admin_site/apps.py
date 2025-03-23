from django.contrib.admin.apps import AdminConfig


class CustomAdminSiteConfig(AdminConfig):
    default_auto_field = "django.db.models.BigAutoField"
    default_site = "autopurchases.admin_site.admin.CustomAdminSite"
