"""Opt-in delivery of visitor-specific fragments alongside shared page HTML."""

from copy import copy
from urllib.parse import urlsplit

from django import forms
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotFound, QueryDict
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from wagtail.models import Page, Site

from wagtail_personalisation.adapters import prepare_personalisation
from wagtail_personalisation.models import PersonalisablePageMixin


class NavigationContextForm(forms.Form):
    page_url = forms.URLField(required=False, max_length=8192, assume_scheme="https")
    referrer = forms.URLField(required=False, max_length=8192, assume_scheme="https")

    def clean(self):
        data = super().clean()
        for field in ("page_url", "referrer"):
            value = data.get(field)
            if value and urlsplit(value).scheme not in ("http", "https"):
                self.add_error(field, "An HTTP or HTTPS URL is required.")
        return data


class DeferredPersonalisationMixin:
    """Add before Page in the bases of page types that opt into fragments."""

    personalisation_deferred = True
    personalisation_fragment_template = None
    personalisation_url_name = "wagtail_personalisation_fragments:page"

    def supports_personalisation_fragments(self):
        # Importing the forms models without the optional app installed can
        # register models whose database tables do not exist.
        if apps.is_installed("wagtail.contrib.forms"):
            from wagtail.contrib.forms.models import FormMixin

            if isinstance(self, FormMixin):
                return False
        return self.personalisation_deferred and not isinstance(
            self, PersonalisablePageMixin
        )

    def should_defer_personalisation(self, request):
        return (
            self.supports_personalisation_fragments()
            and request.method in ("GET", "HEAD")
            and not request.user.is_authenticated
            and not getattr(request, "is_preview", False)
            and not self.get_view_restrictions().exists()
        )

    def get_personalisation_url(self):
        return reverse(self.personalisation_url_name, args=[self.pk])

    def get_personalisation_template(self):
        if not self.personalisation_fragment_template:
            raise ImproperlyConfigured(
                "Set personalisation_fragment_template on the page or override "
                "get_personalisation_template()."
            )
        return self.personalisation_fragment_template

    def get_personalisation_context(self, request):
        """Override to select site-specific content using the evaluated segments."""
        adapter = prepare_personalisation(request, self)
        return {"personalisation_segments": adapter.get_segments()}

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        if request is None:
            return context
        if getattr(request, "_personalisation_deferred", False):
            context["personalisation_url"] = self.get_personalisation_url()
        else:
            prepare_personalisation(request, self)
            context.update(self.get_personalisation_context(request))
        return context

    def serve_preview(self, request, mode_name):
        response = super().serve_preview(request, mode_name)
        add_never_cache_headers(response)
        return response

    def serve(self, request, *args, **kwargs):
        response = super().serve(request, *args, **kwargs)
        if not getattr(request, "_personalisation_deferred", False):
            add_never_cache_headers(response)
        return response


@method_decorator(never_cache, name="dispatch")
class PersonalisationFragmentsView(View):
    """Render opted-in public page fragments, never a full page or a variant."""

    http_method_names = ["get"]

    def get_page(self, request, page_id):
        site = Site.find_for_request(request)
        if site is None:
            raise Http404
        page = (
            Page.objects.live()
            .descendant_of(site.root_page, inclusive=True)
            .filter(pk=page_id)
            .specific()
            .first()
        )
        if (
            not isinstance(page, DeferredPersonalisationMixin)
            or not page.supports_personalisation_fragments()
            or page.get_view_restrictions().exists()
        ):
            raise Http404
        return page

    def get_navigation_request(self, request, page):
        form = NavigationContextForm(
            {
                "page_url": request.headers.get("X-Personalisation-Page-Url", ""),
                "referrer": request.headers.get("X-Personalisation-Referrer", ""),
            }
        )
        if not form.is_valid():
            return None
        page_url = urlsplit(request.build_absolute_uri(page.get_url(request=request)))
        navigation_url = (
            urlsplit(form.cleaned_data["page_url"])
            if form.cleaned_data["page_url"]
            else page_url
        )
        if (navigation_url.scheme, navigation_url.netloc) != (
            request.scheme,
            request.get_host(),
        ) or navigation_url.path != page_url.path:
            return None
        # Keep the authenticated user, session, client IP and other headers from the
        # real request, while rules see the URL/referrer of the page being viewed.
        navigation_request = copy(request)
        navigation_request.META = request.META.copy()
        navigation_request.META.update(
            {
                "PATH_INFO": page_url.path,
                "QUERY_STRING": navigation_url.query,
                "HTTP_REFERER": form.cleaned_data["referrer"],
            }
        )
        navigation_request.__dict__.pop("headers", None)
        navigation_request.path = page_url.path
        navigation_request.path_info = page_url.path
        navigation_request.GET = QueryDict(navigation_url.query)
        return navigation_request

    def get(self, request, page_id):
        try:
            page = self.get_page(request, page_id)
        except Http404:
            return HttpResponseNotFound()
        navigation_request = self.get_navigation_request(request, page)
        if navigation_request is None:
            return HttpResponseBadRequest("Invalid personalisation navigation context.")
        template = page.get_personalisation_template()
        prepare_personalisation(navigation_request, page)
        context = page.get_personalisation_context(navigation_request)
        context.update({"page": page, "self": page})
        return TemplateResponse(navigation_request, template, context)
