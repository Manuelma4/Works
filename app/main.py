import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import PROJECT_ROOT, settings
from app.database import Base, engine, get_db
from app.models import Application, Interview
from app.schemas import (
    ApplicationUpdate,
    GenerateApplicationRequest,
    InterviewCreate,
    ProfilePayload,
)
from app.services.excel import STATUSES, build_workbook
from app.services.generation import generate_application
from app.services.latex import render_documents
from app.services.offers import fetch_offer_text
from app.services.profile import get_or_create_profile, reset_profile, save_profile


app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "app" / "static"), name="static")
templates = Jinja2Templates(directory=PROJECT_ROOT / "app" / "templates")


@app.on_event("startup")
def startup() -> None:
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def _application_dict(item: Application) -> dict[str, Any]:
    return {
        "id": item.id,
        "company": item.company,
        "role": item.role,
        "url": item.url,
        "source": item.source,
        "location": item.location,
        "work_mode": item.work_mode,
        "contract_type": item.contract_type,
        "language": item.language,
        "salary": item.salary,
        "status": item.status,
        "fit_score": item.fit_score,
        "analysis": json.loads(item.analysis_json or "{}"),
        "applied_at": item.applied_at.isoformat() if item.applied_at else None,
        "next_follow_up": item.next_follow_up.isoformat() if item.next_follow_up else None,
        "contact_name": item.contact_name,
        "contact_email": item.contact_email,
        "outcome": item.outcome,
        "rejection_reason": item.rejection_reason,
        "notes": item.notes,
        "has_cv": bool(item.cv_path),
        "has_letter": bool(item.letter_path),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "interviews": [
            {
                "id": interview.id,
                "kind": interview.kind,
                "scheduled_at": interview.scheduled_at.isoformat() if interview.scheduled_at else None,
                "interviewer": interview.interviewer,
                "meeting_url": interview.meeting_url,
                "result": interview.result,
                "notes": interview.notes,
            }
            for interview in item.interviews
        ],
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.app_name,
            "ai_configured": bool(settings.openai_api_key),
            "statuses": STATUSES,
        },
    )


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "ai_configured": bool(settings.openai_api_key),
        "model": settings.openai_model if settings.openai_api_key else "local-fallback",
        "latex": Path(settings.miktex_bin, "xelatex.exe").exists(),
    }


@app.get("/api/profile")
def profile_get(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"data": get_or_create_profile(db)}


@app.put("/api/profile")
def profile_put(payload: ProfilePayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"data": save_profile(db, payload.data)}


@app.post("/api/profile/reset")
def profile_reset(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"data": reset_profile(db)}


@app.get("/api/applications")
def applications_list(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    items = db.scalars(
        select(Application)
        .options(selectinload(Application.interviews))
        .order_by(Application.created_at.desc())
    ).all()
    return [_application_dict(item) for item in items]


@app.post("/api/applications/generate")
def applications_generate(
    payload: GenerateApplicationRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    offer_text = payload.offer_text.strip()
    if len(offer_text) < 30 and payload.url:
        try:
            offer_text = fetch_offer_text(payload.url)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    profile = get_or_create_profile(db)
    try:
        bundle, generation_engine = generate_application(
            offer_text, profile, payload.preferred_language
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Document generation failed: {exc}") from exc

    analysis = bundle.analysis
    item = Application(
        company=analysis.company,
        role=analysis.role,
        url=payload.url,
        source=payload.source,
        location=analysis.location,
        work_mode=analysis.work_mode,
        contract_type=analysis.contract_type,
        language=analysis.language,
        salary=analysis.salary,
        status="Analizada",
        fit_score=analysis.fit_score,
        offer_text=offer_text,
        analysis_json=json.dumps(
            {**analysis.model_dump(), "generation_engine": generation_engine},
            ensure_ascii=False,
        ),
        generated_content_json=bundle.model_dump_json(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    try:
        cv_path, letter_path = render_documents(item.id, bundle, profile)
        item.cv_path = str(cv_path)
        item.letter_path = str(letter_path)
        item.generated_content_json = bundle.model_dump_json()
        item.status = "Documentos listos"
        db.commit()
        db.refresh(item)
    except Exception as exc:
        item.notes = f"LaTeX generation error: {exc}"
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"The offer was analyzed, but PDF compilation failed: {exc}",
        ) from exc
    item = db.scalar(
        select(Application)
        .where(Application.id == item.id)
        .options(selectinload(Application.interviews))
    )
    return _application_dict(item)


@app.patch("/api/applications/{application_id}")
def application_update(
    application_id: int,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.get(Application, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Application not found")
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] not in STATUSES:
        raise HTTPException(status_code=422, detail="Unknown status")
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit()
    item = db.scalar(
        select(Application)
        .where(Application.id == application_id)
        .options(selectinload(Application.interviews))
    )
    return _application_dict(item)


@app.post("/api/applications/{application_id}/interviews")
def interview_create(
    application_id: int,
    payload: InterviewCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.get(Application, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Application not found")
    interview = Interview(application_id=application_id, **payload.model_dump())
    db.add(interview)
    if item.status not in {"Oferta", "Rechazada", "Retirada", "Archivada"}:
        item.status = "Entrevista RH" if "rh" in payload.kind.lower() else "Entrevista técnica"
    db.commit()
    db.refresh(interview)
    return {"id": interview.id}


def _document_response(application_id: int, kind: str, db: Session) -> FileResponse:
    item = db.get(Application, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Application not found")
    raw_path = item.cv_path if kind == "cv" else item.letter_path
    if not raw_path:
        raise HTTPException(status_code=404, detail="Document not generated")
    path = Path(raw_path).resolve()
    if settings.generated_dir.resolve() not in path.parents or not path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.get("/api/applications/{application_id}/cv")
def application_cv(application_id: int, db: Session = Depends(get_db)) -> FileResponse:
    return _document_response(application_id, "cv", db)


@app.get("/api/applications/{application_id}/letter")
def application_letter(application_id: int, db: Session = Depends(get_db)) -> FileResponse:
    return _document_response(application_id, "letter", db)


@app.get("/api/export.xlsx")
def export_excel(db: Session = Depends(get_db)) -> StreamingResponse:
    return StreamingResponse(
        build_workbook(db),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=seguimiento_candidaturas.xlsx"},
    )
