# Deferred personalisation

Deferred delivery separates public page HTML from visitor-specific HTML fragments.
The page response contains placeholders. A small browser loader requests the
fragments separately, allowing the page to be served from a shared cache while
personalisation continues to use the visitor's session.

This is an opt-in feature. Existing pages, whole-page variants and personalised
StreamField blocks retain their existing delivery behaviour. No migration or
new dependency is required.

## Evaluate segments once per request

For ordinary server rendering, use the new API instead of repeatedly calling
`refresh()`:

```python
from wagtail_personalisation.adapters import evaluate_segments

adapter = evaluate_segments(request)
segments = adapter.get_segments()
```

`evaluate_segments()` evaluates at most once per request and applies a valid
superuser `?segment=<id>` override after evaluation. Repeated calls preserve
that override and do not increment the segment counters again. The page-serving
hooks use the same API.

`adapter.ensure_segments_evaluated()` performs the evaluation without applying
an editor override. `adapter.refresh()` remains an explicit re-evaluation and
still updates counters each time it is called. Custom adapters should inherit
`BaseSegmentsAdapter` and call its initializer.

`prepare_personalisation(request, page)` records a page visit before evaluating
segments. Repeating it for the same page/request does not record another visit.
The default hooks and fragment view use it or its component helpers. The
low-level `adapter.add_page_visit(page)` retains its existing counting behaviour.

## Enable fragment URLs

Include the package URLs **before** Wagtail's catch-all page URLs:

```python
from django.urls import include, path
from wagtail import urls as wagtail_urls

urlpatterns = [
    path("personalisation/fragments/", include("wagtail_personalisation.urls")),
    path("", include(wagtail_urls)),
]
```

The default URL name is `wagtail_personalisation_fragments:page`. If you include
the URLs under another namespace, set `personalisation_url_name` on your page.

## Opt in a page type

Put `DeferredPersonalisationMixin` before `Page` (or your site's base page) in
the inheritance list:

```python
from wagtail.models import Page
from wagtail_personalisation.delivery import DeferredPersonalisationMixin

class ArticlePage(DeferredPersonalisationMixin, Page):
    personalisation_fragment_template = "articles/personalisation_fragments.html"

    def get_personalisation_context(self, request):
        context = super().get_personalisation_context(request)
        context["audience_names"] = [
            segment.name for segment in context["personalisation_segments"]
        ]
        return context
```

Replace the example audience names with your own snippet or content selection.
The same context method supplies both inline and deferred rendering. Use
`get_personalisation_template()` if template selection needs to be dynamic.
The fragment template receives `page`, `self` and the normal request context
processors.

Anonymous GET and HEAD requests to public pages defer personalisation. Signed-in
visitors, previews, restricted pages and other HTTP methods render inline with
private/no-store headers. Wagtail form pages and pages using
`PersonalisablePageMixin` are excluded from fragment delivery. Set
`personalisation_deferred = False` to keep a page type inline, or override
`should_defer_personalisation(request)` to narrow the policy further.

The package makes its decision in a `before_serve_page` hook with order `-100`,
before its normal tracking and segmentation hooks construct an adapter. Direct
`page.serve()` calls and previews use inline rendering; they do not run Wagtail's
normal page-serving hook chain.

## Add slots and a fragment template

In the page template, render a shared fallback when deferring and your normal
content when rendering inline:

```html+django
{% load static %}
{% if personalisation_url %}
    <div data-personalisation-url="{{ personalisation_url }}">
        <div data-personalisation-slot="message">Welcome to our site.</div>
    </div>
    <script src="{% static 'wagtail_personalisation/js/fragments.js' %}" defer></script>
{% else %}
    {% include "includes/audience_message.html" %}
{% endif %}
```

In `articles/personalisation_fragments.html`:

```html+django
<template data-personalisation-fragment="message">
    {% include "includes/audience_message.html" %}
</template>
```

Each named fragment replaces the corresponding slot's contents. Multiple slots
can share a name. Empty fragments clear their slots; missing fragments leave
fallback content in place. Keep personalised content out of the shared fallback.

Load the script once per page and normally use a single fragment root containing
all slots, so one page view creates one personalisation request. The loader
fetches each root at most once and uses same-origin credentials and no-store
requests. If JavaScript is disabled or a request fails, fallback content remains.

After insertion, each slot dispatches a bubbling `personalisation:loaded` event.
Initialise your own interactive components using the event's `target` as their
root. `event.detail.name` identifies the fragment. Fetch failures dispatch
`personalisation:error` from the root. For content added dynamically, call
`window.wagtailPersonalisation.load(root)`; it returns a promise resolving to
`true` or `false`.

The loader has no framework or build dependency. Its standalone tests run with
`node --test tests/javascript/fragments.test.cjs` on Node.js 18 or newer.

## Original navigation and rule compatibility

The loader sends the current page URL and `document.referrer` in
`X-Personalisation-Page-Url` and `X-Personalisation-Referrer`. The endpoint
validates these as HTTP(S) URLs and requires the page URL to match the current
origin and the selected page's URL path.

Rules and fragment templates receive a copy of the request with the original
page path, query parameters and referrer. The authenticated user, session,
client IP, device headers and other request attributes come from the actual
fragment request. This preserves targeting for query, referral, device,
geography and page-visit rules without storing visitor-specific navigation
values in shared HTML. Browser referrer policies still determine which referrer
information is available.

A direct request without those headers evaluates the page with an empty query
and referrer. Invalid navigation context returns 400 before tracking. Query
parameters on the fragment URL are not used as page query parameters.
Navigation values are targeting inputs, not evidence of permissions.

## Access and caching

The endpoint accepts GET only. It rejects unpublished pages, pages outside the
current site's page tree, pages without fragment support, and pages with view
restrictions (including restrictions inherited from ancestors). It does not
render whole-page variants or bypass restrictions for signed-in visitors.

Custom page-routing or access rules do not automatically run at this endpoint.
If your site has additional access requirements, subclass
`PersonalisationFragmentsView` and enforce them in `get_page()` before returning
a page. Pages with additional personalised server output must stay inline until
that output is also moved into fragments. Page types using custom routing may
need to override `get_navigation_request()` to validate their permitted paths.

Fragment responses, including empty results, rejected pages, invalid navigation
and disallowed methods, receive `private, no-store` headers. The fragment request
owns page tracking, so it continues to work when the HTML is served by a CDN.
Reloading a fragment URL counts another view; repeated calls in one request do
not. Visitors without JavaScript or with failed fragment requests are not counted
by this mechanism.

Deferred page responses do not read or write personalisation session state and
do not evaluate rules. The package does **not** make the entire response public
or remove existing cache protections. Authentication checks and other middleware
can still access sessions and add `Vary: Cookie`, and other site code can set
cookies. Review the complete response and your CDN rules before enabling shared
HTML caching. Keep authentication, previews, form traffic and the fragment URLs
out of shared caches, and purge affected HTML when content or restrictions change.

For lower-level integrations, `defer_personalisation(request)` selects a no-op
adapter that does not access sessions, count visits or query segments. Call it
before constructing any segment adapter; calling it afterwards raises
`RuntimeError`. It does not move content into fragments or set public cache
headers on its own.
