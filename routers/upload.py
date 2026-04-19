import os

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from services import auth, session_store
from services.file_parser import extract_text
from services.rate_limit import UPLOAD_LIMIT, limiter

router = APIRouter()

ALLOWED_EXTENSIONS = {"pdf", "pptx", "txt", "md"}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
_READ_CHUNK = 64 * 1024

_MAGIC_SIGNATURES = {
    "pdf": (b"%PDF-",),
    "pptx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
}


def _validate_magic(ext: str, data: bytes) -> bool:
    signatures = _MAGIC_SIGNATURES.get(ext)
    if not signatures:
        return True
    return any(data.startswith(sig) for sig in signatures)


async def _read_capped(file: UploadFile) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum size of {MAX_UPLOAD_BYTES} bytes.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/upload")
@limiter.limit(UPLOAD_LIMIT)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    session_id: str = Form(None),
    user: dict = auth.CurrentUser,
):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {MAX_UPLOAD_BYTES} bytes.",
        )

    data = await _read_capped(file)
    if not _validate_magic(ext, data):
        raise HTTPException(status_code=400, detail="File content does not match the declared type.")

    session_id = session_store.ensure_session(session_id, user["id"])
    try:
        text = extract_text(data, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read {file.filename}.") from exc

    session = session_store.require_session(session_id, user["id"])
    session_store.update_session(
        session_id, user["id"], {"uploaded_texts": session["uploaded_texts"] + [text]}
    )
    return {
        "session_id": session_id,
        "filename": file.filename,
        "char_count": len(text),
        "preview": text[:300],
    }
