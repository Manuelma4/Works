import json
from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Profile


def _load_seed() -> dict[str, Any]:
    with settings.profile_seed_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_or_create_profile(db: Session) -> dict[str, Any]:
    profile = db.get(Profile, 1)
    if profile is None:
        data = _load_seed()
        profile = Profile(id=1, data_json=json.dumps(data, ensure_ascii=False))
        db.add(profile)
        db.commit()
        return data
    return json.loads(profile.data_json)


def save_profile(db: Session, data: dict[str, Any]) -> dict[str, Any]:
    profile = db.get(Profile, 1)
    payload = json.dumps(data, ensure_ascii=False)
    if profile is None:
        profile = Profile(id=1, data_json=payload)
        db.add(profile)
    else:
        profile.data_json = payload
    db.commit()
    return deepcopy(data)


def reset_profile(db: Session) -> dict[str, Any]:
    return save_profile(db, _load_seed())

