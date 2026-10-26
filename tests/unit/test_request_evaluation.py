import pytest

from tests.factories.rule import QueryRuleFactory, VisitCountRuleFactory
from tests.factories.segment import SegmentFactory
from wagtail_personalisation import adapters, wagtail_hooks


def test_evaluate_once_preserves_override_and_counts_once(rf, user):
    matching = SegmentFactory()
    QueryRuleFactory(segment=matching, parameter="audience", value="student")
    forced = SegmentFactory()
    request = rf.get("/", {"audience": "student", "segment": forced.pk})
    user.is_superuser = True
    request.user = user

    wagtail_hooks.segment_user(None, request, (), {})
    adapter = adapters.get_segment_adapter(request)
    adapter.ensure_segments_evaluated()
    adapters.evaluate_segments(request)

    assert adapter.get_segments() == [forced]
    matching.refresh_from_db()
    assert matching.visit_count == 1
    forced.refresh_from_db()
    assert forced.visit_count == 0


def test_explicit_refresh_still_re_evaluates(rf):
    segment = SegmentFactory()
    QueryRuleFactory(segment=segment, parameter="audience", value="student")
    request = rf.get("/", {"audience": "student"})
    adapter = adapters.get_segment_adapter(request)
    adapter.ensure_segments_evaluated()
    adapter.refresh()
    segment.refresh_from_db()
    assert segment.visit_count == 2


def test_deferred_adapter_never_accesses_session(rf, site, django_assert_num_queries):
    request = rf.get("/")
    del request.session
    adapters.defer_personalisation(request)
    with django_assert_num_queries(0):
        adapter = adapters.get_segment_adapter(request)
        adapter.ensure_segments_evaluated()
        adapter.refresh()
        adapter.add_page_visit(site.root_page)
        adapter.update_visit_count()
        adapter.set_segments([object()])
        assert adapter.get_segments() == []
        assert adapter.get_segments("excluded_segments") == []
        assert adapter.get_segment_by_id(1) is None
        assert adapter.get_visit_count() == 0


def test_deferral_must_precede_adapter_creation(rf):
    request = rf.get("/")
    adapters.get_segment_adapter(request)
    with pytest.raises(RuntimeError, match="before"):
        adapters.defer_personalisation(request)


def test_session_adapter_subclasses_use_existing_user_sessions(
    site, client, user, mocker
):
    class CustomAdapter(adapters.SessionSegmentsAdapter):
        pass

    mocker.patch.object(adapters, "SEGMENT_ADAPTER_CLASS", CustomAdapter)
    rule = VisitCountRuleFactory(counted_page=site.root_page, segment=SegmentFactory())
    session = client.session
    session["visit_count"] = [{"path": "/", "count": 2}]
    session.save()
    client.force_login(user)
    assert rule.test_user(None, user)
    assert rule.get_user_info_string(user) == "2"


def test_invalid_editor_override_is_ignored(rf, user):
    request = rf.get("/", {"segment": "invalid"})
    user.is_superuser = True
    request.user = user
    wagtail_hooks.segment_user(None, request, (), {})
    assert adapters.get_segment_adapter(request).get_segments() == []
