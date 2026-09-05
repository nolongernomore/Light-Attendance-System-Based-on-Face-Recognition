import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.attendance import AttendanceSession, LivenessChallenge
from schemas.common import ok
from services.liveness_service import generate_liveness_challenge


router = APIRouter(prefix="/liveness", tags=["liveness"])


@router.get("/challenge")
def create_challenge(
    session_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    if session_id is None:
        session = (
            db.query(AttendanceSession)
            .filter(AttendanceSession.status == "active")
            .order_by(AttendanceSession.start_time.desc())
            .first()
        )
    else:
        session = (
            db.query(AttendanceSession)
            .filter(AttendanceSession.id == session_id, AttendanceSession.status == "active")
            .first()
        )
    if not session:
        raise HTTPException(status_code=400, detail="当前没有正在进行的考勤")

    result = generate_liveness_challenge()
    result["session_id"] = session.id
    expire_at = datetime.now() + timedelta(seconds=result.get("expire_seconds", 30))
    challenge = LivenessChallenge(
        challenge_id=result["challenge_id"],
        session_id=session.id,
        actions=json.dumps(result["actions"], ensure_ascii=False),
        expire_at=expire_at,
        used=False,
    )
    db.add(challenge)
    db.commit()
    return ok(result, "活体挑战生成成功")
