from urllib.parse import urlsplit

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import Client
from django.urls import reverse
from wagtail.models import PageViewRestriction

from tests.factories.page import ContentPageFactory, RegularPageFactory
from tests.factories.rule import QueryRuleFactory, ReferralRuleFactory
from tests.factories.segment import SegmentFactory
from tests.factories.site import SiteFactory
from tests.site.pages.models import RegularPage
from wagtail_personalisation.adapters import get_segment_adapter


@pytest.fixture
def fragment_page(site, monkeypatch):
    monkeypatch.setattr(RegularPage, "personalisation_deferred", True)

    def context(page, request):
        return {"audiences": get_segment_adapter(request).get_segments()}

    monkeypatch.setattr(RegularPage, "get_personalisation_context", context)
    return site.root_page.get_children().type(RegularPage).first().specific


def fragment_url(page):
    return reverse("wagtail_personalisation_fragments:page", args=[page.pk])


def test_public_html_is_shared_and_leaves_existing_sessions_untouched(
    client, fragment_page
):
    first = client.get(fragment_page.url)
    session = client.session
    session["visit_count"] = [{"id": fragment_page.pk, "path": "/regular/", "count": 3}]
    session.save()
    returning = client.get(fragment_page.url)
    fresh = Client().get(fragment_page.url)
    assert first.status_code == 200
    assert first.content == returning.content == fresh.content
    assert "data-personalisation-url" in first.text
    assert not first.wsgi_request.session.modified
    assert settings.SESSION_COOKIE_NAME not in returning.cookies
    assert client.session["visit_count"][0]["count"] == 3


def test_fragment_uses_original_query_and_referrer_and_counts_once(
    client, fragment_page
):
    segment = SegmentFactory(name="Students", persistent=False)
    QueryRuleFactory(segment=segment, parameter="audience", value="student")
    ReferralRuleFactory(segment=segment, regex_string=r"https://search.example/")
    url = fragment_url(fragment_page)
    response = client.get(
        url,
        headers={
            "Host": "localhost",
            "X-Personalisation-Page-Url": f"http://localhost{urlsplit(fragment_page.url).path}?audience=student",
            "X-Personalisation-Referrer": "https://search.example/results",
        },
    )
    assert response.status_code == 200
    assert "Students" in response.text
    assert "private" in response["Cache-Control"]
    assert "no-store" in response["Cache-Control"]
    assert client.session["visit_count"][0]["count"] == 1
    segment.refresh_from_db()
    assert segment.visit_count == 1
    second = client.get(url)
    assert "Students" not in second.text
    assert "no-store" in second["Cache-Control"]
    assert client.session["visit_count"][0]["count"] == 2


@pytest.mark.parametrize("restriction_type", ["password", "login", "groups"])
def test_restricted_page_and_children_are_rejected(
    client, fragment_page, restriction_type
):
    PageViewRestriction.objects.create(
        page=fragment_page, restriction_type=restriction_type
    )
    child = RegularPageFactory(parent=fragment_page, slug="child")
    for page in (fragment_page, child):
        response = client.get(fragment_url(page))
        assert response.status_code == 404
        assert "no-store" in response["Cache-Control"]
        assert settings.SESSION_COOKIE_NAME not in response.cookies


def test_rejects_unpublished_cross_site_and_variant_pages(client, fragment_page, site):
    unpublished = RegularPageFactory(
        parent=site.root_page, live=False, slug="unpublished"
    )
    other_site = SiteFactory(hostname="other.example")
    other_page = RegularPageFactory(parent=other_site.root_page)
    variant_page = ContentPageFactory(parent=site.root_page, slug="variant-page")
    variant = variant_page.personalisation_metadata.copy_for_segment(SegmentFactory())
    for page in (unpublished, other_page, variant_page, variant):
        response = client.get(fragment_url(page))
        assert response.status_code == 404
        assert settings.SESSION_COOKIE_NAME not in response.cookies


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Personalisation-Page-Url": "https://other.example/regular/"},
        {"X-Personalisation-Page-Url": "http://localhost/wrong/"},
        {"X-Personalisation-Referrer": "javascript:alert(1)"},
    ],
)
def test_invalid_navigation_context_is_rejected_before_tracking(
    client, fragment_page, headers
):
    response = client.get(fragment_url(fragment_page), headers=headers)
    assert response.status_code == 400
    assert "no-store" in response["Cache-Control"]
    assert settings.SESSION_COOKIE_NAME not in response.cookies


def test_fragment_rejects_post_without_creating_session(client, fragment_page):
    response = client.post(fragment_url(fragment_page))
    assert response.status_code == 405
    assert "no-store" in response["Cache-Control"]
    assert settings.SESSION_COOKIE_NAME not in response.cookies


def test_authenticated_pages_render_inline_and_are_private(client, user, fragment_page):
    segment = SegmentFactory(name="Inline students")
    QueryRuleFactory(segment=segment, parameter="audience", value="student")
    client.force_login(user)
    response = client.get(fragment_page.url, {"audience": "student"})
    assert response.status_code == 200
    assert "Inline students" in response.text
    assert "data-personalisation-url" not in response.text
    assert "private" in response["Cache-Control"]
    assert "no-store" in response["Cache-Control"]
    segment.refresh_from_db()
    assert segment.visit_count == 1
    assert client.session["visit_count"][0]["count"] == 1


@pytest.mark.parametrize("preview", [True, False])
def test_preview_and_direct_rendering_evaluate_once(rf, fragment_page, preview):
    segment = SegmentFactory(name="Preview students")
    QueryRuleFactory(segment=segment, parameter="audience", value="student")
    request = rf.get(fragment_page.url, {"audience": "student"})
    request.is_preview = preview
    request.user = AnonymousUser()
    response = (
        fragment_page.serve_preview(request, "")
        if preview
        else fragment_page.serve(request)
    )
    response.render()
    fragment_page.get_context(request)
    assert "Preview students" in response.text
    assert "no-store" in response["Cache-Control"]
    segment.refresh_from_db()
    assert segment.visit_count == 1


def test_default_pages_still_use_inline_package_behaviour(client, site):
    response = client.get(site.root_page.url)
    assert response.status_code == 200
    assert client.session["visit_count"][0]["count"] == 1


@pytest.mark.parametrize("method", ["head", "options", "delete"])
def test_other_fragment_methods_are_private_and_do_not_track(
    client, fragment_page, method
):
    response = getattr(client, method)(fragment_url(fragment_page))
    assert response.status_code == 405
    assert "no-store" in response["Cache-Control"]
    assert settings.SESSION_COOKIE_NAME not in response.cookies


def test_shared_head_request_does_not_track(client, fragment_page):
    response = client.head(fragment_page.url)
    assert response.status_code == 200
    assert settings.SESSION_COOKIE_NAME not in response.cookies
    assert not response.wsgi_request.session.modified


def test_missing_page_and_missing_site_are_private(client, fragment_page):
    from wagtail.models import Site

    missing = client.get(
        reverse("wagtail_personalisation_fragments:page", args=[999999])
    )
    Site.objects.all().delete()
    no_site = client.get(fragment_url(fragment_page))
    for response in (missing, no_site):
        assert response.status_code == 404
        assert "no-store" in response["Cache-Control"]
        assert settings.SESSION_COOKIE_NAME not in response.cookies


def test_form_and_variant_types_do_not_support_fragments(rf, site):
    from django.apps import apps

    from wagtail_personalisation.delivery import DeferredPersonalisationMixin

    # Exercise the exclusion even if a site's page base also includes the mixin.
    site.root_page.personalisation_deferred = True
    assert not DeferredPersonalisationMixin.supports_personalisation_fragments(
        site.root_page
    )

    if not apps.is_installed("wagtail.contrib.forms"):
        pytest.skip("Run with tests.forms_settings to exercise optional form pages.")
    from wagtail.contrib.forms.models import FormMixin

    class FormPage(DeferredPersonalisationMixin, FormMixin):
        template = "pages/form.html"

    page = FormPage()
    assert not page.supports_personalisation_fragments()
    assert not page.should_defer_personalisation(rf.get("/"))
