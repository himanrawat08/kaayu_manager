import json
from datetime import date as date_type

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.social_post import (
    SocialPost,
    PLATFORMS, PLATFORM_LABELS, PLATFORM_EMOJIS, PLATFORM_CHIP_CLS,
    CONTENT_TYPES, CONTENT_TYPE_LABELS,
    POST_STATUSES, POST_STATUS_LABELS, POST_STATUS_CLS,
)
from app.models.task import Task

router = APIRouter(prefix="/social")
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def social_index(
    request: Request,
    platform: str = "",
    status: str = "",
    view: str = "calendar",
    db: Session = Depends(get_db),
):
    query = db.query(SocialPost).order_by(
        SocialPost.scheduled_date.asc().nullslast(), SocialPost.created_at.desc()
    )
    if platform and platform in PLATFORMS:
        query = query.filter(SocialPost.platform == platform)
    if status and status in POST_STATUSES:
        query = query.filter(SocialPost.status == status)
    posts = query.all()

    # For calendar: only posts with a date and not cancelled
    posts_json = json.dumps([
        {
            "id": p.id,
            "date": p.scheduled_date.isoformat(),
            "time": p.scheduled_time or "",
            "platform": p.platform,
            "content_type": p.content_type,
            "caption": p.caption[:80],
            "status": p.status,
            "campaign": p.campaign or "",
        }
        for p in posts
        if p.scheduled_date and p.status != "cancelled"
    ])

    # For edit modal: keyed by post id
    posts_data_json = json.dumps({
        p.id: {
            "platform": p.platform,
            "content_type": p.content_type,
            "caption": p.caption,
            "hashtags": p.hashtags or "",
            "scheduled_date": p.scheduled_date.isoformat() if p.scheduled_date else "",
            "scheduled_time": p.scheduled_time or "",
            "status": p.status,
            "campaign": p.campaign or "",
            "notes": p.notes or "",
        }
        for p in posts
    })

    today = date_type.today()
    return templates.TemplateResponse(
        request,
        "social/index.html",
        {
            "request": request,
            "posts": posts,
            "posts_json": posts_json,
            "posts_data_json": posts_data_json,
            "today_iso": today.isoformat(),
            "view": view,
            "filter_platform": platform,
            "filter_status": status,
            "platforms": PLATFORMS,
            "platform_labels": PLATFORM_LABELS,
            "platform_emojis": PLATFORM_EMOJIS,
            "platform_chip_cls": PLATFORM_CHIP_CLS,
            "content_types": CONTENT_TYPES,
            "content_type_labels": CONTENT_TYPE_LABELS,
            "post_statuses": POST_STATUSES,
            "post_status_labels": POST_STATUS_LABELS,
            "post_status_cls": POST_STATUS_CLS,
        },
    )


@router.post("/new")
def social_create(
    platform: str = Form(...),
    content_type: str = Form("post"),
    caption: str = Form(...),
    hashtags: str = Form(""),
    scheduled_date: str = Form(""),
    scheduled_time: str = Form(""),
    status: str = Form("draft"),
    campaign: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    if platform not in PLATFORMS:
        platform = "instagram"
    if content_type not in CONTENT_TYPES:
        content_type = "post"
    if status not in POST_STATUSES[:2]:
        status = "draft"

    parsed_date = None
    if scheduled_date.strip():
        try:
            parsed_date = date_type.fromisoformat(scheduled_date.strip())
        except ValueError:
            pass

    task_title = f"[{PLATFORM_LABELS.get(platform, platform)}] {caption.strip()[:70]}"
    task = Task(
        title=task_title,
        due_date=parsed_date,
        priority="medium",
        notes=f"Social — {CONTENT_TYPE_LABELS.get(content_type, content_type)}",
    )
    db.add(task)
    db.flush()

    post = SocialPost(
        platform=platform,
        content_type=content_type,
        caption=caption.strip(),
        hashtags=hashtags.strip() or None,
        scheduled_date=parsed_date,
        scheduled_time=scheduled_time.strip() or None,
        status=status,
        campaign=campaign.strip() or None,
        notes=notes.strip() or None,
        task_id=task.id,
    )
    db.add(post)
    db.commit()
    return RedirectResponse(url="/social", status_code=303)


@router.post("/{post_id}/edit")
def social_edit(
    post_id: int,
    platform: str = Form(...),
    content_type: str = Form("post"),
    caption: str = Form(...),
    hashtags: str = Form(""),
    scheduled_date: str = Form(""),
    scheduled_time: str = Form(""),
    status: str = Form("draft"),
    campaign: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    post = db.query(SocialPost).filter(SocialPost.id == post_id).first()
    if not post:
        return RedirectResponse(url="/social", status_code=303)

    if platform not in PLATFORMS:
        platform = post.platform
    if content_type not in CONTENT_TYPES:
        content_type = post.content_type
    if status not in POST_STATUSES:
        status = post.status

    parsed_date = None
    if scheduled_date.strip():
        try:
            parsed_date = date_type.fromisoformat(scheduled_date.strip())
        except ValueError:
            pass

    post.platform = platform
    post.content_type = content_type
    post.caption = caption.strip()
    post.hashtags = hashtags.strip() or None
    post.scheduled_date = parsed_date
    post.scheduled_time = scheduled_time.strip() or None
    post.status = status
    post.campaign = campaign.strip() or None
    post.notes = notes.strip() or None

    if post.task_id:
        task = db.query(Task).filter(Task.id == post.task_id).first()
        if task:
            task.title = f"[{PLATFORM_LABELS.get(platform, platform)}] {caption.strip()[:70]}"
            task.due_date = parsed_date
            if status == "published":
                task.is_completed = True

    db.commit()
    return RedirectResponse(url="/social", status_code=303)


@router.post("/{post_id}/status")
def social_set_status(
    post_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
):
    post = db.query(SocialPost).filter(SocialPost.id == post_id).first()
    if post and status in POST_STATUSES:
        post.status = status
        if status == "published" and post.task_id:
            task = db.query(Task).filter(Task.id == post.task_id).first()
            if task:
                task.is_completed = True
        db.commit()
    return RedirectResponse(url="/social", status_code=303)


@router.post("/{post_id}/delete")
def social_delete(
    post_id: int,
    db: Session = Depends(get_db),
):
    post = db.query(SocialPost).filter(SocialPost.id == post_id).first()
    if post:
        task_id = post.task_id
        db.delete(post)
        db.flush()
        if task_id:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                db.delete(task)
        db.commit()
    return RedirectResponse(url="/social", status_code=303)
