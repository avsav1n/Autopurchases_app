from django.contrib.admin.apps import AdminConfig


class CustomAdminSiteConfig(AdminConfig):
    default_site = "autopurchases.admin_site.admin.CustomAdminSite"
