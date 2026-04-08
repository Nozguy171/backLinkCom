from flask import Blueprint, jsonify, request

from app.models import Video, VideoSection, VideoSectionLink


videos_bp = Blueprint("videos", __name__)


@videos_bp.get("/video-sections")
def list_video_sections():
    items = VideoSection.query.filter_by(is_active=True).order_by(
        VideoSection.display_order.asc(),
        VideoSection.name.asc(),
    ).all()

    return jsonify({"items": [item.to_dict() for item in items]})


@videos_bp.get("/videos")
def list_videos():
    section_slug = (request.args.get("section_slug") or "").strip()
    section_type = (request.args.get("type") or "").strip().lower()

    query = (
        Video.query
        .join(VideoSectionLink, VideoSectionLink.video_id == Video.id)
        .join(VideoSection, VideoSection.id == VideoSectionLink.section_id)
        .filter(Video.is_active.is_(True), VideoSection.is_active.is_(True))
    )

    if section_slug:
        query = query.filter(VideoSection.slug == section_slug)

    if section_type:
        query = query.filter(VideoSection.section_type == section_type)

    items = (
        query
        .distinct()
        .order_by(Video.display_order.asc(), Video.created_at.desc())
        .all()
    )

    return jsonify({"items": [item.to_dict() for item in items]})