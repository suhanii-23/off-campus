import numpy as np
import pytest

from matching import layer2_embeddings
from matching.layer2_embeddings import score_layer2


class FakeModel:
    """Deterministic stand-in for SentenceTransformer, avoids downloading
    the real model for fast unit tests."""

    def __init__(self, vectors):
        self._vectors = vectors

    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        return np.array([self._vectors[t] for t in texts])


def test_identical_texts_score_near_100(mocker):
    vec = np.array([1.0, 0.0, 0.0])
    fake = FakeModel({"same": vec, "same2": vec})
    mocker.patch.object(layer2_embeddings, "get_model", return_value=fake)

    score = score_layer2("same", "same2")
    assert score == pytest.approx(100.0, abs=0.5)


def test_orthogonal_texts_score_near_50(mocker):
    fake = FakeModel({"a": np.array([1.0, 0.0]), "b": np.array([0.0, 1.0])})
    mocker.patch.object(layer2_embeddings, "get_model", return_value=fake)

    score = score_layer2("a", "b")
    assert score == pytest.approx(50.0, abs=0.5)


def test_opposite_texts_score_near_0(mocker):
    fake = FakeModel({"a": np.array([1.0, 0.0]), "b": np.array([-1.0, 0.0])})
    mocker.patch.object(layer2_embeddings, "get_model", return_value=fake)

    score = score_layer2("a", "b")
    assert score == pytest.approx(0.0, abs=0.5)


def test_empty_inputs_score_zero():
    assert score_layer2("", "something") == 0.0
    assert score_layer2("something", "") == 0.0


@pytest.mark.slow
def test_real_model_scores_relevant_job_higher_than_irrelevant_job(profile):
    ai_job = (
        "We are hiring a Machine Learning Engineer to build deep learning "
        "models with PyTorch and deploy computer vision pipelines using "
        "OpenCV and YOLO."
    )
    irrelevant_job = (
        "We are hiring a Warehouse Operations Associate to manage inventory "
        "and coordinate shipments in our logistics facility."
    )
    blurb = profile["profile_blurb"]

    relevant_score = score_layer2(ai_job, blurb)
    irrelevant_score = score_layer2(irrelevant_job, blurb)

    assert relevant_score > irrelevant_score
