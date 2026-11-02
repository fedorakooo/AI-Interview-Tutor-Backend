from shared_models.assessment import (
    AssessmentTemplateSnapshot,
    CustomQuestion,
    FocusArea,
    TemplateDraftRequest,
)
from shared_models.assessment.contracts import slugify_focus_id

from src.domain.exceptions.spec_errors import EmptySpecDraftError
from src.domain.interview.spec_dto import DraftFocus, SpecDraft

MAX_FOCUS_AREAS = 10
MAX_LIST_ITEMS = 10


def build_template(draft: SpecDraft, request: TemplateDraftRequest) -> AssessmentTemplateSnapshot:
    """Normalize a model draft into a valid template, keeping the recruiter text as the brief."""
    focuses = _unique_focuses(draft.focus_areas)
    if not focuses:
        raise EmptySpecDraftError()

    ids = _focus_ids(focuses)
    weights = _normalized_weights([focus.weight for focus in focuses])
    required = _required_flags(focuses, weights)

    criteria = [
        FocusArea(
            id=ids[index],
            skill=_cut(focus.skill, 120),
            what_to_learn=_cut(focus.what_to_learn, 1000),
            required=required[index],
            weight=weights[index],
            expected_level=_cut(focus.expected_level, 64) or "middle",
            guidance=_cut(focus.guidance, 1000),
            method=focus.method,
            strong_signals=_texts(focus.strong_signals),
            weak_signals=_texts(focus.weak_signals),
            must_cover=_texts(focus.must_cover),
            min_evidence=min(max(focus.min_evidence, 1), 5, max(focus.max_questions, 1)),
            max_questions=min(max(focus.max_questions, 1), 10),
        )
        for index, focus in enumerate(focuses)
    ]

    by_skill = {focus.skill.casefold().strip(): ids[index] for index, focus in enumerate(focuses)}
    custom_questions = [
        CustomQuestion(
            focus_id=by_skill[question.focus_skill.casefold().strip()],
            text=_cut(question.text, 1000),
            reference_answer=_cut(question.reference_answer, 2000) if question.reference_answer else None,
            required=question.required,
        )
        for question in draft.custom_questions[:20]
        if question.text.strip() and question.focus_skill.casefold().strip() in by_skill
    ]

    return AssessmentTemplateSnapshot(
        mode=draft.mode,
        question_count=min(max(draft.question_count, len(criteria), 1), 30),
        duration_minutes=min(max(draft.duration_minutes, 5), 180),
        attempt_limit=1,
        criteria=criteria,
        brief=request.brief,
        skip=_texts(draft.skip, 20),
        red_flags=_texts(draft.red_flags, 20),
        custom_questions=custom_questions,
        language=request.language,
        candidate_feedback=request.candidate_feedback,
        cv_policy=request.cv_policy,
    )


def _unique_focuses(focuses: list[DraftFocus]) -> list[DraftFocus]:
    seen: set[str] = set()
    unique: list[DraftFocus] = []
    for focus in focuses:
        key = focus.skill.casefold().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(focus)
    return unique[:MAX_FOCUS_AREAS]


def _focus_ids(focuses: list[DraftFocus]) -> list[str]:
    used: set[str] = set()
    ids: list[str] = []
    for focus in focuses:
        base = slugify_focus_id(focus.skill)
        candidate, suffix = base, 2
        while candidate in used:
            candidate, suffix = f"{base}_{suffix}", suffix + 1
        used.add(candidate)
        ids.append(candidate)
    return ids


def _normalized_weights(raw: list[int]) -> list[int]:
    positive = [max(weight, 1) for weight in raw]
    total = sum(positive)
    weights = [max(1, round(weight * 100 / total)) for weight in positive]
    difference = 100 - sum(weights)
    order = sorted(range(len(weights)), key=lambda index: weights[index], reverse=True)
    position = 0
    while difference != 0:
        index = order[position % len(order)]
        step = 1 if difference > 0 else -1
        if weights[index] + step >= 1:
            weights[index] += step
            difference -= step
        position += 1
    return weights


def _required_flags(focuses: list[DraftFocus], weights: list[int]) -> list[bool]:
    flags = [focus.required for focus in focuses]
    if not any(flags):
        flags[max(range(len(weights)), key=lambda index: weights[index])] = True
    return flags


def _texts(items: list[str], limit: int = MAX_LIST_ITEMS) -> list[str]:
    cleaned = [_cut(item, 300) for item in items if item.strip()]
    return list(dict.fromkeys(cleaned))[:limit]


def _cut(text: str, limit: int) -> str:
    return text.strip()[:limit]
