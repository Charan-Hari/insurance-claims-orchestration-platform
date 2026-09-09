from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewResult:
    recommendation: str
    confidence: str
    reasons: list[str]


def review(filename: str, media_type: str, content: bytes) -> ReviewResult:
    reasons: list[str] = []
    name = filename.lower()
    text = content.decode("utf-8", errors="ignore").lower()
    if not content:
        reasons.append("Document has no content")
    if not name.endswith((".pdf", ".txt", ".csv", ".json", ".png", ".jpg", ".jpeg")):
        reasons.append("File extension is outside the supported review set")
    for term, reason in (
        ("fraud", "Contains the configured fraud investigation keyword"),
        ("excluded", "Contains an exclusion indicator"),
        ("lawsuit", "Contains a litigation indicator"),
    ):
        if term in text:
            reasons.append(reason)
    if "signature" in text and ("missing" in text or "unsigned" in text):
        reasons.append("Signature appears to be missing")
    if reasons:
        return ReviewResult("manual_review", "medium", reasons)
    return ReviewResult("approve", "high", ["No configured escalation rules matched"])
