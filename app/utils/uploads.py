from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "webm", "mkv", "avi", "m4v"}
ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "png", "jpg", "jpeg", "webp"}

def _save_uploaded_file(file_storage, folder: str, allowed_extensions: set[str], error_message: str) -> str:
    if not file_storage or not file_storage.filename:
        raise ValueError("No se recibió ningún archivo.")

    filename = secure_filename(file_storage.filename)
    if "." not in filename:
        raise ValueError("Archivo inválido.")

    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in allowed_extensions:
        raise ValueError(error_message)

    base_dir = Path(current_app.static_folder) / "uploads" / folder
    base_dir.mkdir(parents=True, exist_ok=True)

    final_name = f"{uuid4().hex}.{ext}"
    absolute_path = base_dir / final_name
    file_storage.save(absolute_path)

    return f"/static/uploads/{folder}/{final_name}"


def save_uploaded_image(file_storage, folder: str) -> str:
    return _save_uploaded_file(
        file_storage=file_storage,
        folder=folder,
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
        error_message="Formato no permitido. Usa png, jpg, jpeg o webp.",
    )


def save_uploaded_video(file_storage, folder: str) -> str:
    return _save_uploaded_file(
        file_storage=file_storage,
        folder=folder,
        allowed_extensions=ALLOWED_VIDEO_EXTENSIONS,
        error_message="Formato de video no permitido. Usa mp4, mov, webm, mkv, avi o m4v.",
    )

def save_uploaded_document(file_storage, folder: str) -> str:
    return _save_uploaded_file(
        file_storage=file_storage,
        folder=folder,
        allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS,
        error_message="Formato no permitido. Usa pdf, doc, docx, xls, xlsx, png, jpg, jpeg o webp.",
    )