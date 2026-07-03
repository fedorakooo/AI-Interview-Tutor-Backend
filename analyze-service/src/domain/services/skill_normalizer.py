from src.data.skill_synonyms import SKILL_SYNONYMS
from shared_models.cv.cv_items import SkillItem

MAX_SKILLS = 64


class SkillNormalizer:
    """Normalizes and deduplicates extracted skills without enforcing a closed enum."""

    def __init__(self, synonyms: dict[str, str] | None = None, max_skills: int = MAX_SKILLS):
        self._synonyms = {key.lower(): value for key, value in (synonyms or SKILL_SYNONYMS).items()}
        self._max_skills = max_skills

    def normalize(self, skills: list[SkillItem] | None) -> list[SkillItem]:
        if not skills:
            return []

        normalized: list[SkillItem] = []
        seen: set[str] = set()

        for skill in skills:
            cleaned_name = self._canonical_name(skill.name)
            if not cleaned_name:
                continue

            dedupe_key = cleaned_name.casefold()
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            normalized.append(
                SkillItem(
                    name=cleaned_name,
                    category=self._clean_category(skill.category),
                )
            )

            if len(normalized) >= self._max_skills:
                break

        return normalized

    def _canonical_name(self, raw_name: str) -> str:
        stripped = " ".join(raw_name.split())
        if not stripped:
            return ""

        mapped = self._synonyms.get(stripped.casefold())
        return mapped or stripped

    @staticmethod
    def _clean_category(category: str | None) -> str | None:
        if category is None:
            return None

        cleaned = " ".join(category.split())
        return cleaned or None
