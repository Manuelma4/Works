import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
import pymupdf

from app.config import PROJECT_ROOT, settings
from app.services.generation import GenerationBundle


LATEX_REPLACEMENTS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(value: Any) -> str:
    text = str(value or "")
    return "".join(LATEX_REPLACEMENTS.get(char, char) for char in text)


def _safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return normalized.strip("_")[:80] or "application"


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(PROJECT_ROOT / "app" / "latex"),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tex"] = latex_escape
    return env


def _xelatex_path() -> str:
    configured = Path(settings.miktex_bin) / "xelatex.exe"
    if configured.exists():
        return str(configured)
    discovered = shutil.which("xelatex")
    if discovered:
        return discovered
    raise RuntimeError("XeLaTeX was not found. Install MiKTeX or configure MIKTEX_BIN.")


def _compile(tex_path: Path) -> Path:
    command = [
        _xelatex_path(),
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={tex_path.parent}",
        str(tex_path),
    ]
    environment = os.environ.copy()
    environment["PATH"] = f"{settings.miktex_bin}{os.pathsep}{environment.get('PATH', '')}"
    result = subprocess.run(
        command,
        cwd=tex_path.parent,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        log_tail = "\n".join((result.stdout + result.stderr).splitlines()[-35:])
        raise RuntimeError(f"XeLaTeX failed:\n{log_tail}")
    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        raise RuntimeError("XeLaTeX completed without producing a PDF.")
    return pdf_path


def _pdf_fill_ratio(pdf_path: Path) -> float:
    document = pymupdf.open(pdf_path)
    if len(document) != 1:
        return 1.0
    page = document[0]
    lowest_text = max(
        (block[3] for block in page.get_text("blocks") if block[4].strip()),
        default=0,
    )
    return lowest_text / page.rect.height


def render_documents(
    application_id: int,
    bundle: GenerationBundle,
    profile: dict[str, Any],
) -> tuple[Path, Path]:
    target_dir = settings.generated_dir / str(application_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    language = bundle.analysis.language
    person = profile["person"]
    context = {
        "bundle": bundle.model_dump(),
        "person": person,
        "profile": profile,
        "language": language,
        "today": __import__("datetime").date.today(),
        "font_dir": (PROJECT_ROOT / "app" / "latex" / "fonts").as_posix() + "/",
        "signature_path": "",
        "section_extra_pt": 0.0,
        "letter_extra_pt": 0.0,
    }
    signature_path = PROJECT_ROOT / "app" / "latex" / "assets" / "manuel-maya-signature.png"
    if signature_path.exists():
        context["signature_path"] = signature_path.as_posix()
    env = _environment()
    base = _safe_filename(f"{bundle.analysis.company}_{bundle.analysis.role}")
    cv_tex = target_dir / f"CV_Manuel_Maya_{base}.tex"
    letter_tex = target_dir / f"Motivation_Manuel_Maya_{base}.tex"
    cv_tex.write_text(env.get_template("cv.tex.j2").render(**context), encoding="utf-8")
    letter_tex.write_text(env.get_template("letter.tex.j2").render(**context), encoding="utf-8")
    cv_pdf = _compile(cv_tex)
    _compile(cv_tex)

    # Tighten content progressively. Projects and useful evidence should not
    # disappear just because the first rich draft slightly exceeds one page.
    compaction_steps = [
        {"experience_bullets": 3, "project_bullets": 2, "skill_items": 8},
        {"experience_bullets": 2, "project_bullets": 2, "skill_items": 7},
        {"experience_bullets": 2, "project_bullets": 1, "skill_items": 6},
        {"experience_bullets": 1, "project_bullets": 1, "skill_items": 6},
    ]
    for step in compaction_steps:
        if len(pymupdf.open(cv_pdf)) == 1:
            break
        for experience in bundle.cv.experiences:
            experience.bullets = experience.bullets[: step["experience_bullets"]]
        for project in bundle.cv.projects:
            project.bullets = project.bullets[: step["project_bullets"]]
        for group in bundle.cv.skill_groups:
            group.items = group.items[: step["skill_items"]]
        context["bundle"] = bundle.model_dump()
        cv_tex.write_text(env.get_template("cv.tex.j2").render(**context), encoding="utf-8")
        cv_pdf = _compile(cv_tex)

    if len(pymupdf.open(cv_pdf)) > 1:
        raise RuntimeError("The tailored CV could not be reduced to one A4 page.")

    # Distribute a modest amount of the remaining whitespace between sections.
    # This targets a visually balanced 93–97% page fill without inserting a
    # single artificial blank block near the footer.
    fill_ratio = _pdf_fill_ratio(cv_pdf)
    if fill_ratio < 0.93 or fill_ratio > 0.97:
        section_count = 5 if bundle.cv.projects else 4
        page_height = pymupdf.open(cv_pdf)[0].rect.height
        section_extra = (0.95 - fill_ratio) * page_height / section_count
        section_extra = max(-1.5, min(6.0, section_extra))
        context["section_extra_pt"] = section_extra
        cv_tex.write_text(env.get_template("cv.tex.j2").render(**context), encoding="utf-8")
        adjusted_pdf = _compile(cv_tex)
        if len(pymupdf.open(adjusted_pdf)) == 1:
            adjusted_fill = _pdf_fill_ratio(adjusted_pdf)
            if 0.93 <= adjusted_fill <= 0.97:
                cv_pdf = adjusted_pdf
    letter_pdf = _compile(letter_tex)
    letter_fill = _pdf_fill_ratio(letter_pdf)
    if letter_fill < 0.90 or letter_fill > 0.96:
        gap_count = len(bundle.letter.paragraphs) + 5
        page_height = pymupdf.open(letter_pdf)[0].rect.height
        letter_extra = (0.92 - letter_fill) * page_height / gap_count
        context["letter_extra_pt"] = max(-3.0, min(8.0, letter_extra))
        letter_tex.write_text(
            env.get_template("letter.tex.j2").render(**context),
            encoding="utf-8",
        )
        adjusted_letter = _compile(letter_tex)
        if len(pymupdf.open(adjusted_letter)) == 1:
            letter_pdf = adjusted_letter
    return cv_pdf, letter_pdf
