import os
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..activity import record_activity
from ..models import Document
from ..security import current_user
from ..storage_service import upload_document, read_document, delete_document

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    name = Path(file.filename or "file.bin").name
    stored = uuid.uuid4().hex + Path(name).suffix.lower()
    content_type = file.content_type or "application/octet-stream"
    limit = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024

    content = bytearray()
    while chunk := await file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > limit:
            raise HTTPException(413, "File too large")

    try:
        upload_document(stored, bytes(content), content_type)
    except Exception:
        raise HTTPException(502, "Document upload to storage failed")

    try:
        d = Document(
            owner_id=u.id,
            original_name=name,
            stored_name=stored,
            content_type=content_type,
            size=len(content),
        )
        db.add(d)
        db.commit()
        db.refresh(d)
    except Exception:
        db.rollback()
        try:
            delete_document(stored)
        except Exception:
            pass
        raise HTTPException(500, "Document record could not be saved")

    record_activity(
        u.id,
        "document.upload",
        "document",
        d.id,
        {
            "file_size_bytes": len(content),
            "content_type": content_type,
            "file_extension": Path(name).suffix.lstrip("."),
        },
    )

    return {
        "id": d.id,
        "name": name,
        "size": len(content),
        "content_type": content_type,
    }


@router.get("")
def listing(db: Session = Depends(get_db), u=Depends(current_user)):
    return [
        {"id": d.id, "name": d.original_name, "size": d.size}
        for d in db.query(Document).filter_by(owner_id=u.id).all()
    ]


@router.get("/{doc_id}/download")
def download(
    doc_id: int,
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    d = db.query(Document).filter_by(id=doc_id, owner_id=u.id).first()
    if not d:
        raise HTTPException(404, "Document not found")

    try:
        content = read_document(d.stored_name)
    except Exception:
        raise HTTPException(404, "Document file is no longer available")

    filename = quote(d.original_name)
    return Response(
        content=content,
        media_type=d.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        },
    )


@router.delete("/{doc_id}")
def delete(
    doc_id: int,
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    d = db.query(Document).filter_by(id=doc_id, owner_id=u.id).first()
    if not d:
        raise HTTPException(404, "Document not found")

    try:
        delete_document(d.stored_name)
    except Exception:
        raise HTTPException(502, "Document could not be deleted from storage")

    document_id = d.id
    db.delete(d)
    db.commit()

    record_activity(u.id, "document.delete", "document", document_id)
    return {"success": True}
