import django

# Override the manifest-based static files storage so tests don't require
# a `collectstatic` run to resolve {% static %} template tags.
django.conf.settings.STATICFILES_STORAGE = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
)
