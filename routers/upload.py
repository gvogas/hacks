from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from services import session_store
from services.file_parser import extract_text

router = APIRouter()

ALLOWED_EXTENSIONS = {"pdf", "pptx", "txt", "md"}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(None),
):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    session_id = session_store.ensure_session(session_id)
    data = await file.read()
    text = extract_text(data, file.filename)

    session = session_store.get_session(session_id)
    existing = session.get("uploaded_texts", [])
    existing.append(text)
    session_store.update_session(session_id, {"uploaded_texts": existing})

    return {
        "session_id": session_id,
        "filename": file.filename,
        "char_count": len(text),
        "preview": text[:300],
    }
