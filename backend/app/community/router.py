from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from ..core.config import settings
from ..core.security import get_current_user, get_optional_user
from ..database.database import get_db
from ..database.models import Discussion, DiscussionComment, Issue, IssueComment, Notification, Resource, User, UserFollow
from .schemas import (
    DISCUSSION_STATUSES, ISSUE_PRIORITIES, ISSUE_STATUSES, ISSUE_TYPES, DiscussionCommentCreate, DiscussionCommentRead,
    DiscussionCommentUpdate, DiscussionCreate, DiscussionListResponse, DiscussionRead, DiscussionUpdate, FollowListResponse,
    FollowState, IssueCommentCreate, IssueCommentRead, IssueCommentUpdate, IssueCreate, IssueListResponse, IssueRead,
    IssueUpdate, NotificationListResponse, NotificationRead, UnreadCount,
)
from .service import CommunityService


resource_router = APIRouter(prefix="/api/resources/{resource_id}", tags=["Community"])
router = APIRouter(prefix="/api", tags=["Community"])
notifications_router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def discussion_query():
    return select(Discussion).options(selectinload(Discussion.author), selectinload(Discussion.resource), selectinload(Discussion.comments).selectinload(DiscussionComment.author))


def issue_query():
    return select(Issue).options(selectinload(Issue.author), selectinload(Issue.assignee), selectinload(Issue.resource), selectinload(Issue.comments).selectinload(IssueComment.author))


def discussion_or_404(db: Session, discussion_id: int, user: User | None = None) -> Discussion:
    item = db.execute(discussion_query().where(Discussion.id == discussion_id)).unique().scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="讨论不存在")
    CommunityService.require_visible_resource(db, item.resource_id, user)
    if item.is_hidden:
        raise HTTPException(status_code=404, detail="讨论不存在")
    return item


def issue_or_404(db: Session, issue_id: int, user: User | None = None) -> Issue:
    item = db.execute(issue_query().where(Issue.id == issue_id)).unique().scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Issue 不存在")
    CommunityService.require_visible_resource(db, item.resource_id, user)
    if item.is_hidden:
        raise HTTPException(status_code=404, detail="Issue 不存在")
    return item


@resource_router.post("/discussions", response_model=DiscussionRead, status_code=201)
def create_discussion(resource_id: int, payload: DiscussionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    CommunityService.enforce_rate_limit("discussion", current_user.id, settings.discussion_rate_limit)
    resource = CommunityService.require_visible_resource(db, resource_id, current_user)
    item = Discussion(resource_id=resource.id, author_id=current_user.id, title=payload.title, content=payload.content)
    db.add(item)
    db.flush()
    CommunityService.activity(db, resource.id, "DISCUSSION_CREATED", current_user.id, item.title)
    CommunityService.notify_resource_owner(db, resource, current_user, "DISCUSSION_CREATED", f"New discussion on {resource.title}", item.title, "DISCUSSION", item.id)
    db.commit(); db.refresh(item)
    return CommunityService.discussion_detail(discussion_or_404(db, item.id, current_user))


@resource_router.get("/discussions", response_model=DiscussionListResponse)
def list_discussions(resource_id: int, status_filter: str | None = Query(None, alias="status"), sort: str = Query("newest", pattern="^(newest|oldest|most_commented)$"), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    CommunityService.require_visible_resource(db, resource_id, current_user)
    if status_filter and status_filter.upper() not in DISCUSSION_STATUSES: raise HTTPException(422, "status 不支持")
    suffix = f"{status_filter or 'all'}:{sort}:{page}:{page_size}"
    if current_user is None:
        cached = CommunityService.get_cached_list("discussions", resource_id, suffix)
        if cached: return cached
    query = discussion_query().where(Discussion.resource_id == resource_id, Discussion.is_hidden.is_(False))
    if status_filter: query = query.where(Discussion.status == status_filter.upper())
    count = int(db.scalar(select(func.count(Discussion.id)).where(Discussion.resource_id == resource_id, Discussion.is_hidden.is_(False), *([] if not status_filter else [Discussion.status == status_filter.upper()]))) or 0)
    ordering = Discussion.updated_at.desc() if sort == "newest" else Discussion.created_at.asc() if sort == "oldest" else Discussion.comments_count.desc()
    items = db.scalars(query.order_by(Discussion.is_pinned.desc(), ordering, Discussion.id.desc()).offset((page-1)*page_size).limit(page_size)).unique().all()
    payload = {"items": [CommunityService.discussion_summary(x) for x in items], "page": page, "page_size": page_size, "total": count}
    if current_user is None: CommunityService.set_cached_list("discussions", resource_id, suffix, payload)
    return payload


@router.get("/discussions/{discussion_id}", response_model=DiscussionRead)
def get_discussion(discussion_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    return CommunityService.discussion_detail(discussion_or_404(db, discussion_id, current_user))


@router.patch("/discussions/{discussion_id}", response_model=DiscussionRead)
def update_discussion(discussion_id: int, payload: DiscussionUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = discussion_or_404(db, discussion_id, current_user)
    if item.author_id != current_user.id: raise HTTPException(403, "只有讨论作者可以编辑")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    db.commit(); CommunityService.invalidate_community_list("discussions", item.resource_id)
    return CommunityService.discussion_detail(discussion_or_404(db, discussion_id, current_user))


def discussion_action(discussion_id: int, action: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = discussion_or_404(db, discussion_id, current_user); resource = item.resource
    owner = resource.author_id == current_user.id; author = item.author_id == current_user.id
    if action == "close":
        if not (owner or author): raise HTTPException(403, "没有管理讨论的权限")
        item.status = "CLOSED"
        CommunityService.activity(db, resource.id, "DISCUSSION_CLOSED", current_user.id, item.title)
    elif action == "reopen":
        if not (owner or author): raise HTTPException(403, "没有管理讨论的权限")
        item.status = "OPEN"
        CommunityService.activity(db, resource.id, "DISCUSSION_REOPENED", current_user.id, item.title)
    elif action == "lock":
        CommunityService.require_resource_owner(resource, current_user); item.is_locked = True
    elif action == "unlock":
        CommunityService.require_resource_owner(resource, current_user); item.is_locked = False
    else: raise HTTPException(404, "操作不存在")
    db.commit(); CommunityService.invalidate_community_list("discussions", item.resource_id)
    return CommunityService.discussion_detail(discussion_or_404(db, discussion_id, current_user))


@router.post("/discussions/{discussion_id}/close", response_model=DiscussionRead)
def close_discussion(discussion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return discussion_action(discussion_id, "close", db, current_user)


@router.post("/discussions/{discussion_id}/reopen", response_model=DiscussionRead)
def reopen_discussion(discussion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return discussion_action(discussion_id, "reopen", db, current_user)


@router.post("/discussions/{discussion_id}/lock", response_model=DiscussionRead)
def lock_discussion(discussion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return discussion_action(discussion_id, "lock", db, current_user)


@router.post("/discussions/{discussion_id}/unlock", response_model=DiscussionRead)
def unlock_discussion(discussion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return discussion_action(discussion_id, "unlock", db, current_user)


@router.post("/discussions/{discussion_id}/pin", response_model=DiscussionRead)
def pin_discussion(discussion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = discussion_or_404(db, discussion_id, current_user); CommunityService.require_resource_owner(item.resource, current_user)
    item.is_pinned = True
    db.commit(); CommunityService.invalidate_community_list("discussions", item.resource_id)
    return CommunityService.discussion_detail(discussion_or_404(db, discussion_id, current_user))


@router.delete("/discussions/{discussion_id}/pin", response_model=DiscussionRead)
def unpin_discussion(discussion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = discussion_or_404(db, discussion_id, current_user); CommunityService.require_resource_owner(item.resource, current_user); item.is_pinned = False
    db.commit(); CommunityService.invalidate_community_list("discussions", item.resource_id)
    return CommunityService.discussion_detail(discussion_or_404(db, discussion_id, current_user))


@router.post("/discussions/{discussion_id}/comments", response_model=DiscussionCommentRead, status_code=201)
def comment_discussion(discussion_id: int, payload: DiscussionCommentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    CommunityService.enforce_rate_limit("comment", current_user.id, settings.comment_rate_limit)
    item = discussion_or_404(db, discussion_id, current_user)
    if item.is_locked or item.status == "CLOSED": raise HTTPException(409, "讨论已锁定或关闭，不能继续评论")
    if payload.parent_id:
        parent = db.get(DiscussionComment, payload.parent_id)
        if parent is None or parent.discussion_id != item.id or parent.parent_id is not None: raise HTTPException(422, "只能回复一级评论")
    comment = DiscussionComment(discussion_id=item.id, author_id=current_user.id, content=payload.content, parent_id=payload.parent_id)
    db.add(comment); item.comments_count += 1; CommunityService.activity(db, item.resource_id, "COMMENT_ADDED", current_user.id, item.title)
    CommunityService.create_notification(db, item.author_id, current_user.id, "DISCUSSION_COMMENTED", "New reply on your discussion", item.title, "DISCUSSION", item.id)
    db.commit(); db.refresh(comment)
    payload = CommunityService.discussion_comment_tree([comment])
    return payload[0] if payload else {
        "id": comment.id, "discussion_id": comment.discussion_id, "parent_id": comment.parent_id,
        "content": comment.content, "is_deleted": comment.is_deleted, "is_hidden": comment.is_hidden,
        "author": CommunityService.user_summary(comment.author), "created_at": comment.created_at,
        "updated_at": comment.updated_at, "replies": [],
    }


@router.patch("/comments/{comment_id}", response_model=DiscussionCommentRead)
def update_discussion_comment(comment_id: int, payload: DiscussionCommentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.get(DiscussionComment, comment_id)
    if item is None: raise HTTPException(404, "评论不存在")
    discussion_or_404(db, item.discussion_id, current_user)
    if item.author_id != current_user.id or item.is_deleted or item.is_hidden: raise HTTPException(403, "只有评论作者可以编辑")
    item.content = payload.content; db.commit(); db.refresh(item)
    return CommunityService.discussion_comment_tree([item])[0]


@router.delete("/comments/{comment_id}", status_code=204)
def delete_discussion_comment(comment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.get(DiscussionComment, comment_id)
    if item is None: raise HTTPException(404, "评论不存在")
    discussion_or_404(db, item.discussion_id, current_user)
    if item.author_id != current_user.id: raise HTTPException(403, "只有评论作者可以删除")
    if not item.is_deleted:
        item.is_deleted = True; item.content = ""
        discussion = db.get(Discussion, item.discussion_id)
        if discussion is not None:
            discussion.comments_count = max((discussion.comments_count or 0) - 1, 0)
        db.commit()
        if discussion is not None:
            CommunityService.invalidate_community_list("discussions", discussion.resource_id)


@resource_router.post("/issues", response_model=IssueRead, status_code=201)
def create_issue(resource_id: int, payload: IssueCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    CommunityService.enforce_rate_limit("issue", current_user.id, settings.issue_rate_limit)
    resource = CommunityService.require_visible_resource(db, resource_id, current_user)
    item = Issue(resource_id=resource.id, author_id=current_user.id, title=payload.title, description=payload.description, issue_type=payload.issue_type)
    db.add(item); db.flush(); CommunityService.activity(db, resource.id, "ISSUE_CREATED", current_user.id, item.title)
    CommunityService.notify_resource_owner(db, resource, current_user, "ISSUE_CREATED", f"New issue on {resource.title}", item.title, "ISSUE", item.id)
    db.commit(); CommunityService.invalidate_community_list("issues", resource.id); db.refresh(item)
    return CommunityService.issue_detail(issue_or_404(db, item.id, current_user))


@resource_router.get("/issues", response_model=IssueListResponse)
def list_issues(resource_id: int, status_filter: str | None = Query(None, alias="status"), issue_type: str | None = None, priority: str | None = None, author: str | None = None, assignee: str | None = None, sort: str = Query("newest", pattern="^(newest|oldest|priority|most_commented)$"), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    CommunityService.require_visible_resource(db, resource_id, current_user)
    suffix = ":".join(str(value or "all") for value in (status_filter, issue_type, priority, author, assignee, sort, page, page_size))
    if current_user is None:
        cached = CommunityService.get_cached_list("issues", resource_id, suffix)
        if cached:
            return cached
    query = issue_query().where(Issue.resource_id == resource_id, Issue.is_hidden.is_(False))
    count_query = select(func.count(Issue.id)).where(Issue.resource_id == resource_id, Issue.is_hidden.is_(False))
    filters=[]
    if status_filter:
        if status_filter.upper() not in ISSUE_STATUSES: raise HTTPException(422, "status 不支持")
        filters.append(Issue.status == status_filter.upper())
    if issue_type:
        if issue_type.upper() not in ISSUE_TYPES: raise HTTPException(422, "issue_type 不支持")
        filters.append(Issue.issue_type == issue_type.upper())
    if priority:
        if priority.upper() not in ISSUE_PRIORITIES: raise HTTPException(422, "priority 不支持")
        filters.append(Issue.priority == priority.upper())
    if author:
        query=query.join(Issue.author).where(User.username == author)
        count_query=count_query.join(Issue.author).where(User.username == author)
    if assignee:
        query=query.join(Issue.assignee).where(User.username == assignee)
        count_query=count_query.join(Issue.assignee).where(User.username == assignee)
    query=query.where(*filters); count=int(db.scalar(count_query.where(*filters)) or 0)
    priority_order = case(
        (Issue.priority == "CRITICAL", 4),
        (Issue.priority == "HIGH", 3),
        (Issue.priority == "MEDIUM", 2),
        (Issue.priority == "LOW", 1),
        else_=0,
    )
    order = Issue.updated_at.desc() if sort=="newest" else Issue.created_at.asc() if sort=="oldest" else Issue.comments_count.desc() if sort=="most_commented" else priority_order.desc()
    items=db.scalars(query.order_by(order, Issue.id.desc()).offset((page-1)*page_size).limit(page_size)).unique().all()
    payload = {"items":[CommunityService.issue_summary(x) for x in items],"page":page,"page_size":page_size,"total":count}
    if current_user is None:
        CommunityService.set_cached_list("issues", resource_id, suffix, payload)
    return payload


@router.get("/issues/{issue_id}", response_model=IssueRead)
def get_issue(issue_id:int, db:Session=Depends(get_db), current_user:User|None=Depends(get_optional_user)): return CommunityService.issue_detail(issue_or_404(db, issue_id, current_user))


@router.patch("/issues/{issue_id}", response_model=IssueRead)
def update_issue(issue_id:int,payload:IssueUpdate,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    item=issue_or_404(db,issue_id,current_user); values=payload.model_dump(exclude_unset=True); owner=item.resource.author_id==current_user.id; author=item.author_id==current_user.id
    privileged={k:v for k,v in values.items() if k in {"status","priority","assignee_id"}}
    editable={k:v for k,v in values.items() if k in {"title","description"}}
    if editable and not author: raise HTTPException(403,"只有 Issue 作者可以编辑标题和描述")
    if privileged and not owner:
        if set(privileged)=={"status"} and privileged["status"]=="CLOSED" and author: pass
        else: raise HTTPException(403,"只有资源作者可以管理 Issue")
    if "assignee_id" in privileged and privileged["assignee_id"] not in {None, item.resource.author_id}: raise HTTPException(422,"V1 只允许将 Issue 指派给资源作者或取消负责人")
    for key,value in values.items(): setattr(item,key,value)
    if "status" in values:
        item.closed_at=datetime.utcnow() if values["status"] in {"RESOLVED","CLOSED"} else None
        CommunityService.activity(db,item.resource_id,"ISSUE_RESOLVED" if values["status"]=="RESOLVED" else "ISSUE_STATUS_CHANGED",current_user.id,f"{item.title}: {values['status']}")
        CommunityService.create_notification(db,item.author_id,current_user.id,"ISSUE_STATUS_CHANGED","Issue status updated",f"{item.title} is now {values['status']}.","ISSUE",item.id)
    db.commit(); CommunityService.invalidate_community_list("issues",item.resource_id)
    return CommunityService.issue_detail(issue_or_404(db,issue_id,current_user))


@router.post("/issues/{issue_id}/comments",response_model=IssueCommentRead,status_code=201)
def comment_issue(issue_id:int,payload:IssueCommentCreate,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    CommunityService.enforce_rate_limit("comment",current_user.id,settings.comment_rate_limit); item=issue_or_404(db,issue_id,current_user)
    if item.status in {"RESOLVED", "CLOSED"}:
        raise HTTPException(409, "Issue 已解决或关闭，不能继续评论")
    if payload.parent_id:
        parent=db.get(IssueComment,payload.parent_id)
        if parent is None or parent.issue_id != item.id or parent.parent_id is not None: raise HTTPException(422,"只能回复一级评论")
    comment=IssueComment(issue_id=item.id,author_id=current_user.id,content=payload.content,parent_id=payload.parent_id); db.add(comment); item.comments_count+=1
    CommunityService.activity(db,item.resource_id,"COMMENT_ADDED",current_user.id,item.title); CommunityService.create_notification(db,item.author_id,current_user.id,"ISSUE_COMMENTED","New reply on your issue",item.title,"ISSUE",item.id)
    db.commit(); CommunityService.invalidate_community_list("issues", item.resource_id); db.refresh(comment);
    payload = CommunityService.issue_comment_tree([comment])
    return payload[0] if payload else {
        "id": comment.id, "issue_id": comment.issue_id, "parent_id": comment.parent_id,
        "content": comment.content, "is_deleted": comment.is_deleted, "is_hidden": comment.is_hidden,
        "author": CommunityService.user_summary(comment.author), "created_at": comment.created_at,
        "updated_at": comment.updated_at, "replies": [],
    }


@router.patch("/issue-comments/{comment_id}",response_model=IssueCommentRead)
def update_issue_comment(comment_id:int,payload:IssueCommentUpdate,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    item=db.get(IssueComment,comment_id)
    if item is None: raise HTTPException(404,"评论不存在")
    issue_or_404(db,item.issue_id,current_user)
    if item.author_id != current_user.id or item.is_deleted: raise HTTPException(403,"只有评论作者可以编辑")
    item.content=payload.content;db.commit();db.refresh(item);return CommunityService.issue_comment_tree([item])[0]


@router.delete("/issue-comments/{comment_id}",status_code=204)
def delete_issue_comment(comment_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    item=db.get(IssueComment,comment_id)
    if item is None: raise HTTPException(404,"评论不存在")
    issue_or_404(db,item.issue_id,current_user)
    if item.author_id != current_user.id: raise HTTPException(403,"只有评论作者可以删除")
    if not item.is_deleted:
        item.is_deleted=True;item.content=""
        issue=db.get(Issue,item.issue_id)
        if issue is not None:
            issue.comments_count=max((issue.comments_count or 0)-1,0)
        db.commit();CommunityService.invalidate_community_list("issues", issue.resource_id if issue else 0)


@router.get("/notifications",response_model=NotificationListResponse)
def list_notifications(unread_only:bool=False,limit:int=Query(50,ge=1,le=100),db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    query=select(Notification).options(selectinload(Notification.actor)).where(Notification.user_id==current_user.id)
    if unread_only: query=query.where(Notification.is_read.is_(False))
    items=db.scalars(query.order_by(Notification.created_at.desc()).limit(limit)).all()
    return {"items":[CommunityService.notification_dict(x) for x in items],"unread_count":CommunityService.unread_count(db,current_user.id)}


@notifications_router.get("/unread-count",response_model=UnreadCount)
def unread_notifications(db:Session=Depends(get_db),current_user:User=Depends(get_current_user)): return {"unread_count":CommunityService.unread_count(db,current_user.id)}


@notifications_router.post("/{notification_id}/read",response_model=UnreadCount)
def read_notification(notification_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    item=db.scalar(select(Notification).where(Notification.id==notification_id,Notification.user_id==current_user.id))
    if item is None: raise HTTPException(404,"通知不存在")
    item.is_read=True;db.commit();CommunityService.invalidate_unread_count(current_user.id);return {"unread_count":CommunityService.unread_count(db,current_user.id)}


@notifications_router.post("/read-all",response_model=UnreadCount)
def read_all_notifications(db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    for item in db.scalars(select(Notification).where(Notification.user_id==current_user.id,Notification.is_read.is_(False))).all(): item.is_read=True
    db.commit();CommunityService.invalidate_unread_count(current_user.id);return {"unread_count":0}
