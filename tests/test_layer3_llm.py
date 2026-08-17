from types import SimpleNamespace

from collectors.base import RawJob
from matching import layer3_llm
from matching.layer3_llm import call_layer3_api, make_cached_layer3_fn


def make_job(**overrides) -> RawJob:
    defaults = dict(
        ats_type="greenhouse",
        ats_job_id="1",
        title="Product Engineer",
        company_name="Acme",
        location_raw="Bengaluru, India",
        description_raw="Build RAG pipelines and LLM applications.",
        apply_url="https://example.com/jobs/1",
    )
    defaults.update(overrides)
    return RawJob(**defaults)


def fake_tool_response(data: dict):
    tool_block = SimpleNamespace(type="tool_use", input=data)
    return SimpleNamespace(content=[tool_block])


def fake_client(data: dict):
    response = fake_tool_response(data)
    create = lambda **kwargs: response
    return SimpleNamespace(messages=SimpleNamespace(create=create))


def test_call_layer3_api_parses_tool_use_response(mocker, profile):
    data = {
        "score": 88,
        "categories": ["AI_SOFTWARE", "LLM_GENAI"],
        "experience_fit": "Strong",
        "india_eligible": True,
        "reasons": ["Heavy LLM/RAG focus despite generic title"],
    }
    mocker.patch.object(layer3_llm, "get_client", return_value=fake_client(data))

    result, raw = call_layer3_api(make_job(), profile)

    assert result.score == 88.0
    assert result.categories == ["AI_SOFTWARE", "LLM_GENAI"]
    assert result.experience_fit == "Strong"
    assert result.india_eligible is True
    assert "LLM: Heavy LLM/RAG focus despite generic title" in result.reasons
    assert raw == data


def test_cached_layer3_fn_uses_cache_without_calling_api(mocker, profile):
    existing_job = SimpleNamespace(
        score_layer3=91.0,
        layer3_raw_response={
            "categories": ["AI_ML"],
            "experience_fit": "Strong",
            "india_eligible": True,
            "reasons": ["cached reason"],
        },
    )
    mock_call = mocker.patch.object(layer3_llm, "call_layer3_api")

    fn = make_cached_layer3_fn(existing_job=existing_job)
    result = fn(make_job(), profile)

    assert result.score == 91.0
    assert "AI_ML" in result.categories
    mock_call.assert_not_called()


def test_cached_layer3_fn_calls_api_and_stores_on_existing_job(mocker, profile):
    existing_job = SimpleNamespace(score_layer3=None, layer3_raw_response=None)
    data = {
        "score": 75,
        "categories": ["BACKEND"],
        "experience_fit": "Moderate",
        "india_eligible": True,
        "reasons": ["decent fit"],
    }
    mocker.patch.object(layer3_llm, "call_layer3_api", return_value=(
        layer3_llm.Layer3Result(75.0, ["BACKEND"], "Moderate", True, ["LLM: decent fit"]),
        data,
    ))

    fn = make_cached_layer3_fn(existing_job=existing_job)
    result = fn(make_job(), profile)

    assert result.score == 75.0
    assert existing_job.layer3_raw_response == data
    assert existing_job.score_layer3 == 75.0


def test_cached_layer3_fn_returns_none_on_api_failure_without_raising(mocker, profile):
    mocker.patch.object(layer3_llm, "call_layer3_api", side_effect=RuntimeError("API down"))

    fn = make_cached_layer3_fn(existing_job=None)
    result = fn(make_job(), profile)

    assert result is None
