MODEL_NAME = "all-MiniLM-L6-v2"
MAX_CHARS = 1500  # roughly within MiniLM's ~256 token window; longer JDs are truncated

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def score_layer2(job_description: str, profile_blurb: str) -> float:
    """Cosine similarity between the job description and the candidate's
    profile blurb, rescaled from [-1, 1] to a 0-100 score."""
    if not job_description or not profile_blurb:
        return 0.0

    model = get_model()
    embeddings = model.encode(
        [job_description[:MAX_CHARS], profile_blurb[:MAX_CHARS]],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    cosine_sim = float(embeddings[0] @ embeddings[1])
    return max(0.0, min(100.0, (cosine_sim + 1) / 2 * 100))
