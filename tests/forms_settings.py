from tests.settings import *  # noqa: F403
from tests.settings import INSTALLED_APPS

INSTALLED_APPS = (*INSTALLED_APPS, "wagtail.contrib.forms")
