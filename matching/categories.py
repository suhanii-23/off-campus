CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "SOFTWARE": [
        "software engineer",
        "software developer",
        "software development",
        "codebase",
        "engineering team",
        "write code",
        "ship code",
    ],
    "BACKEND": [
        "backend",
        "back-end",
        "back end",
        "server-side",
        "rest api",
        "restful",
        "microservice",
        "distributed system",
        "database",
    ],
    "AI_ML": [
        "machine learning",
        "deep learning",
        "artificial intelligence",
        "neural network",
        "model training",
        "pytorch",
        "tensorflow",
        "scikit-learn",
        "keras",
        "ml model",
    ],
    "AI_SOFTWARE": [
        "ai-powered",
        "ai powered",
        "intelligent application",
        "ai application",
        "ai product",
        "ai integration",
        "llm integration",
        "building ai",
        "foundation model",
    ],
    "LLM_GENAI": [
        "llm",
        "large language model",
        "generative ai",
        "genai",
        " rag ",
        "retrieval augmented generation",
        "retrieval-augmented generation",
        "prompt engineering",
        "fine-tun",
        "finetun",
        "langchain",
        "vector database",
        "embedding model",
        "qlora",
        "lora",
    ],
    "COMPUTER_VISION": [
        "computer vision",
        "opencv",
        "yolo",
        "image segmentation",
        "object detection",
        "image classification",
        "clip model",
        "image recognition",
    ],
    "NLP": [
        "natural language processing",
        " nlp ",
        "text classification",
        "named entity",
        "tokeniz",
        "sentiment analysis",
        "language model",
    ],
    "MLOPS": [
        "mlops",
        "ml pipeline",
        "model deployment",
        "model serving",
        "model monitoring",
        "feature store",
    ],
    "ML_INFRASTRUCTURE": [
        "ml infrastructure",
        "training infrastructure",
        "distributed training",
        "gpu cluster",
        "inference infrastructure",
        "vllm",
        "model inference",
    ],
    "PLATFORM": [
        "platform engineer",
        "developer platform",
        "internal platform",
        "infrastructure engineer",
        "platform team",
    ],
    "FULL_STACK": [
        "full stack",
        "full-stack",
        "fullstack",
        "frontend and backend",
        "react",
        "frontend",
    ],
    "SYSTEMS": [
        "systems engineer",
        "operating system",
        "distributed systems",
        "low-level",
        "systems programming",
        "kernel",
    ],
}


def categorize(text: str) -> list[str]:
    """Multi-label category tagging from free text (title + description).

    Recall-biased: a single keyword hit is enough to tag a category, since
    the goal is to surface AI/software-adjacent roles even when the title
    alone gives no hint (e.g. a "Product Engineer" posting whose body is
    full of LLM/RAG language should still get tagged AI_SOFTWARE/LLM_GENAI).
    """
    lowered = f" {text.lower()} "
    matched = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            matched.append(category)
    return matched
