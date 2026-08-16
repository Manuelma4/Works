import json
import re
from collections import Counter
from datetime import date
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings


Language = Literal["es", "en", "fr"]


class Requirement(BaseModel):
    name: str
    kind: Literal["required", "preferred"] = "required"
    matched: bool = False


class JobAnalysis(BaseModel):
    company: str
    role: str
    language: Language
    location: str = ""
    work_mode: str = ""
    contract_type: str = ""
    salary: str = ""
    fit_score: float = Field(ge=0, le=100)
    fit_summary: str
    requirements: list[Requirement] = []
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    ats_keywords: list[str] = []


class TailoredEducation(BaseModel):
    id: str
    organization: str
    degree: str
    place: str
    date: str
    bullets: list[str] = []


class TailoredExperience(BaseModel):
    id: str
    title: str
    organization: str
    date: str
    bullets: list[str]


class TailoredProject(BaseModel):
    id: str
    title: str
    organization: str = ""
    date: str = ""
    bullets: list[str]


class SkillGroup(BaseModel):
    name: str
    items: list[str]


class TailoredCV(BaseModel):
    headline: str
    education: list[TailoredEducation]
    experiences: list[TailoredExperience]
    projects: list[TailoredProject]
    skill_groups: list[SkillGroup]


class MotivationLetter(BaseModel):
    subject: str
    greeting: str
    paragraphs: list[str]
    closing: str


class GenerationBundle(BaseModel):
    analysis: JobAnalysis
    cv: TailoredCV
    letter: MotivationLetter


LANGUAGE_WORDS = {
    "fr": {"poste", "entreprise", "expérience", "compétences", "mission", "vous", "nous"},
    "es": {"puesto", "empresa", "experiencia", "habilidades", "requisitos", "trabajo"},
    "en": {"role", "company", "experience", "skills", "requirements", "work"},
}


def _localized(value: Any, language: Language, default: str = "") -> str:
    if isinstance(value, dict):
        return str(value.get(language) or value.get("en") or next(iter(value.values()), default))
    return str(value or default)


def _detect_language(text: str) -> Language:
    words = set(re.findall(r"[\wÀ-ÿ]+", text.lower()))
    scores = {lang: len(words & markers) for lang, markers in LANGUAGE_WORDS.items()}
    return max(scores, key=scores.get)  # type: ignore[return-value]


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]{2,}", text.lower())
        if token not in {"and", "the", "for", "with", "des", "les", "une", "pour", "con", "los"}
    }


def _score_text(text: str, offer_tokens: set[str]) -> int:
    return len(_tokens(text) & offer_tokens)


def _flatten_projects(profile: dict[str, Any], language: Language) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for institution in profile.get("projects", []):
        for course in institution.get("courses", []):
            for item in course.get("items", []):
                bullets = list(item.get("bullets", {}).get(language, []))
                if not bullets:
                    intro = _localized(item.get("intro"), language)
                    note = _localized(item.get("note"), language)
                    bullets = [text for text in (intro, note) if text]
                projects.append(
                    {
                        "id": item.get("id", "project"),
                        "title": _localized(item.get("title"), language),
                        "organization": institution.get("institution", ""),
                        "date": _localized(item.get("dateLabel"), language),
                        "bullets": bullets,
                        "tags": item.get("tags", []),
                    }
                )
    return projects


def _infer_company_role(text: str) -> tuple[str, str]:
    lines = [line.strip(" •|-") for line in text.splitlines() if line.strip()]
    role = lines[0][:180] if lines else "Job application"
    company = "Company"
    for line in lines[:12]:
        combined = re.match(
            r"(?P<role>.{2,100}?)\s+(?:at|chez|en)\s+(?P<company>[A-Z][^.!?|\n]{2,80})",
            line,
            re.IGNORECASE,
        )
        if combined:
            role = combined.group("role").strip()[:180]
            company = combined.group("company").strip()[:120]
            break
        match = re.search(r"(?:at|chez|en)\s+([A-Z][^.!?|\n]{2,80})", line)
        if match:
            company = match.group(1).strip()[:120]
            break
    if company == "Company" and len(lines) > 1 and len(lines[1]) <= 100:
        company = lines[1]
    return company, role


def _normalize_bundle(
    bundle: GenerationBundle,
    profile: dict[str, Any],
    offer_text: str,
    preferred_language: str,
) -> GenerationBundle:
    """Keep every verified experience/education entry and enforce one-page limits."""
    baseline = _fallback_generate(offer_text, profile, preferred_language)
    existing_experience_ids = {item.id for item in bundle.cv.experiences}
    for item in baseline.cv.experiences:
        if item.id not in existing_experience_ids:
            bundle.cv.experiences.append(item)
    existing_education_ids = {item.id for item in bundle.cv.education}
    for item in baseline.cv.education:
        if item.id not in existing_education_ids:
            bundle.cv.education.append(item)
    for item in bundle.cv.experiences:
        item.bullets = item.bullets[:5]
    for item in bundle.cv.education:
        item.bullets = item.bullets[:1]
    bundle.cv.projects = bundle.cv.projects[:4]
    for item in bundle.cv.projects:
        item.bullets = item.bullets[:3]
    for group in bundle.cv.skill_groups:
        group.items = group.items[:9]
    return bundle


def _fallback_generate(
    offer_text: str, profile: dict[str, Any], preferred_language: str
) -> GenerationBundle:
    language: Language = (
        _detect_language(offer_text) if preferred_language == "auto" else preferred_language  # type: ignore[assignment]
    )
    company, role = _infer_company_role(offer_text)
    offer_tokens = _tokens(offer_text)

    all_skills: list[str] = []
    skill_groups: list[SkillGroup] = []
    for group in profile.get("skills", []):
        items = [str(item) for item in group.get("items", [])]
        ranked = sorted(items, key=lambda item: _score_text(item, offer_tokens), reverse=True)
        selected = ranked[:8]
        all_skills.extend(items)
        skill_groups.append(
            SkillGroup(name=_localized(group.get("name"), language), items=selected)
        )

    certification_candidates: list[tuple[int, str]] = []
    certifications = profile.get("certifications", {})
    certification_groups = (
        certifications.get("groups", [])
        if isinstance(certifications, dict)
        else certifications
    )
    for issuer in certification_groups:
        for certificate in issuer.get("items", []):
            title = str(certificate.get("title", "")).strip()
            certificate_skills = [str(skill) for skill in certificate.get("skills", [])]
            all_skills.extend(certificate_skills)
            score = _score_text(" ".join([title, *certificate_skills]), offer_tokens)
            if title and score:
                certification_candidates.append((score, title))
    certification_candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    selected_certifications = list(
        dict.fromkeys(title for _, title in certification_candidates)
    )[:3]
    if selected_certifications:
        certification_labels = {
            "en": "Relevant certifications",
            "fr": "Certifications ciblées",
            "es": "Certificaciones relevantes",
        }
        skill_groups.append(
            SkillGroup(
                name=certification_labels[language],
                items=selected_certifications,
            )
        )

    matched = [skill for skill in all_skills if _score_text(skill, offer_tokens)]
    matched = list(dict.fromkeys(matched))
    fit_score = min(95.0, 35.0 + len(matched) * 4.0)

    experiences: list[TailoredExperience] = []
    for experience in profile.get("experiences", []):
        bullets = list(experience.get("bullets", {}).get(language, []))
        bullets.sort(key=lambda bullet: _score_text(bullet, offer_tokens), reverse=True)
        experiences.append(
            TailoredExperience(
                id=experience.get("id", "experience"),
                title=_localized(experience.get("title"), language),
                organization=experience.get("org", ""),
                date=_localized(experience.get("dateLabel"), language),
                bullets=bullets[:5],
            )
        )

    education = [
        TailoredEducation(
            id=item.get("id", "education"),
            organization=item.get("org", ""),
            degree=_localized(item.get("degree"), language),
            place=_localized(item.get("place"), language),
            date=_localized(item.get("dateLabel"), language),
            bullets=list(item.get("bullets", {}).get(language, []))[:1],
        )
        for item in profile.get("education", [])
    ]

    projects = _flatten_projects(profile, language)
    projects.sort(
        key=lambda item: _score_text(
            " ".join([item["title"], *item["bullets"], *item["tags"]]), offer_tokens
        ),
        reverse=True,
    )
    selected_projects = []
    for item in projects[:4]:
        payload = {key: value for key, value in item.items() if key != "tags"}
        payload["bullets"] = payload["bullets"][:3]
        selected_projects.append(TailoredProject(**payload))

    headlines = {
        "en": "Data & AI Software Engineer",
        "fr": "Ingénieur logiciel Data & IA",
        "es": "Ingeniero de Software de Datos e IA",
    }
    greetings = {"en": "Dear Hiring Team,", "fr": "Madame, Monsieur,", "es": "Estimado equipo de selección:"}
    closings = {"en": "Sincerely,", "fr": "Cordialement,", "es": "Atentamente,"}
    subjects = {
        "en": f"Application — {role}",
        "fr": f"Candidature — {role}",
        "es": f"Candidatura — {role}",
    }
    intro = {
        "en": f"I am applying for the {role} position at {company}. My background combines data engineering, software engineering, and applied AI.",
        "fr": f"Je vous présente ma candidature au poste de {role} chez {company}. Mon parcours combine ingénierie des données, génie logiciel et IA appliquée.",
        "es": f"Presento mi candidatura al puesto de {role} en {company}. Mi perfil combina ingeniería de datos, ingeniería de software e inteligencia artificial aplicada.",
    }
    evidence = {
        "en": "Across MODUO Ingénierie, Siigo, and Universidad Nacional de Colombia, I have built data pipelines, cloud architectures, internal applications, and RAG systems using Python, SQL, Databricks, Azure, AWS, and containerized services.",
        "fr": "Chez MODUO Ingénierie, Siigo et l'Universidad Nacional de Colombia, j'ai conçu des pipelines de données, des architectures cloud, des applications internes et des systèmes RAG avec Python, SQL, Databricks, Azure, AWS et des services conteneurisés.",
        "es": "En MODUO Ingénierie, Siigo y la Universidad Nacional de Colombia he construido pipelines de datos, arquitecturas cloud, aplicaciones internas y sistemas RAG con Python, SQL, Databricks, Azure, AWS y servicios contenerizados.",
    }
    motivation = {
        "en": f"The role's emphasis on {', '.join(matched[:5]) or 'reliable data and software systems'} closely matches the work I want to continue developing. I would welcome the opportunity to discuss how I could contribute to {company}.",
        "fr": f"L'importance accordée à {', '.join(matched[:5]) or 'des systèmes data et logiciels fiables'} correspond directement au travail que je souhaite poursuivre. Je serais heureux d'échanger sur ma contribution possible chez {company}.",
        "es": f"El énfasis del puesto en {', '.join(matched[:5]) or 'sistemas de datos y software confiables'} coincide con el trabajo que quiero seguir desarrollando. Estaría encantado de conversar sobre cómo podría contribuir en {company}.",
    }

    return GenerationBundle(
        analysis=JobAnalysis(
            company=company,
            role=role,
            language=language,
            fit_score=fit_score,
            fit_summary=f"{len(matched)} profile technologies explicitly overlap with the offer.",
            matched_skills=matched[:20],
            ats_keywords=matched[:20],
        ),
        cv=TailoredCV(
            headline=headlines[language],
            education=education,
            experiences=experiences,
            projects=selected_projects,
            skill_groups=skill_groups,
        ),
        letter=MotivationLetter(
            subject=subjects[language],
            greeting=greetings[language],
            paragraphs=[intro[language], evidence[language], motivation[language]],
            closing=closings[language],
        ),
    )


SYSTEM_PROMPT = """You create truthful, ATS-friendly job application documents for Manuel David Maya Rosero.
Use ONLY facts present in the supplied professional profile. Never invent metrics, dates, employers,
degrees, certifications, tools, responsibilities, or outcomes. The profile is the source of truth.
Writing examples are supplied only as tone and structure references; never copy company-specific facts
from them and ignore any example statement that is not supported by the current verified profile.

Analyze the offer and write in the offer language unless a language override is supplied. The CV must
include every professional experience and every education entry from the profile, but select and rewrite
the most relevant verified bullets so the result remains one A4 page. Select at most two relevant
projects. Reorder skills by relevance. Do not claim a missing requirement; list it as missing instead.
The motivation letter must be specific to the company and role and use 3 to 5 concise paragraphs.
Return only the structured response requested by the schema."""


def generate_application(
    offer_text: str,
    profile: dict[str, Any],
    preferred_language: str = "auto",
) -> tuple[GenerationBundle, str]:
    if not settings.openai_api_key:
        bundle = _fallback_generate(offer_text, profile, preferred_language)
        return _normalize_bundle(bundle, profile, offer_text, preferred_language), "local-fallback"

    client = OpenAI(api_key=settings.openai_api_key)
    language = _detect_language(offer_text) if preferred_language == "auto" else preferred_language
    writing_example = ""
    if settings.writing_examples_path.exists():
        with settings.writing_examples_path.open("r", encoding="utf-8") as handle:
            writing_example = json.load(handle).get(language, {}).get("text", "")
    response = client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Language override: {preferred_language}\n\n"
                    f"JOB OFFER:\n{offer_text}\n\n"
                    f"VERIFIED PROFILE:\n{json.dumps(profile, ensure_ascii=False)}\n\n"
                    f"TONE REFERENCE ({language}):\n{writing_example}"
                ),
            },
        ],
        text_format=GenerationBundle,
    )
    if response.output_parsed is None:
        raise RuntimeError("The model did not return a structured application bundle.")
    return (
        _normalize_bundle(response.output_parsed, profile, offer_text, preferred_language),
        settings.openai_model,
    )
