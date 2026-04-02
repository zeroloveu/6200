import os
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.sessions import SessionMiddleware

from .chain_service import (
    ChainServiceError,
    build_address_url,
    build_tx_url,
    deploy_poll_contract,
    fetch_contract_summary,
    fetch_voter_action,
    get_chain_config,
    is_chain_ready,
)
from .database import get_db, init_db
from .models import Poll, PollVote, User, naive_utc_now
from .security import hash_password, verify_password


BASE_DIR = Path(__file__).resolve().parent
USERNAME_PATTERN = re.compile(r"^[a-z0-9_.-]{3,32}$")
WALLET_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
TX_HASH_PATTERN = re.compile(r"^0x[a-fA-F0-9]{64}$")
APP_TIMEZONE = ZoneInfo("Asia/Shanghai")
APP_SESSION_HTTPS_ONLY = (os.getenv("APP_SESSION_HTTPS_ONLY", "false").strip().lower() == "true")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Vote Station Hybrid", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("APP_SECRET_KEY", "replace-me-in-production"),
    same_site="lax",
    https_only=APP_SESSION_HTTPS_ONLY,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def utc_naive_to_local(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC).astimezone(APP_TIMEZONE).replace(tzinfo=None)


def local_naive_to_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=APP_TIMEZONE).astimezone(UTC).replace(tzinfo=None)


templates.env.filters["format_dt"] = (
    lambda value: utc_naive_to_local(value).strftime("%Y-%m-%d %H:%M") if value else ""
)
templates.env.filters["input_dt"] = (
    lambda value: utc_naive_to_local(value).strftime("%Y-%m-%dT%H:%M") if value else ""
)


def now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def normalize_username(raw_username: str) -> str:
    return raw_username.strip().lower()


def normalize_wallet_address(raw_wallet_address: str) -> str:
    wallet_address = raw_wallet_address.strip()
    if not wallet_address:
        return ""
    if not WALLET_PATTERN.match(wallet_address):
        raise ValueError("钱包地址格式不正确，必须是 0x 开头的 42 位地址。")
    return wallet_address.lower()


def parse_collection(raw_value: str) -> list[str]:
    normalized = raw_value.replace("\r", "\n")
    for separator in [",", ";", "\n"]:
        normalized = normalized.replace(separator, "\n")

    items: list[str] = []
    seen: set[str] = set()
    for piece in normalized.split("\n"):
        value = piece.strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        items.append(value)
    return items


def parse_datetime_field(value: str, field_name: str) -> datetime:
    try:
        return local_naive_to_utc(datetime.fromisoformat(value))
    except ValueError as exc:
        raise ValueError(f"{field_name} 格式不正确，请重新选择。") from exc


def get_current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    return db.get(User, user_id) if user_id else None


def flash(request: Request, category: str, text: str) -> None:
    messages = request.session.get("messages", [])
    messages.append({"category": category, "text": text})
    request.session["messages"] = messages


def pop_messages(request: Request) -> list[dict[str, str]]:
    return request.session.pop("messages", [])


def render_page(
    request: Request,
    db: Session,
    template_name: str,
    context: dict | None = None,
    current_user: User | None = None,
) -> HTMLResponse:
    payload = context or {}
    payload.update(
        {
            "request": request,
            "current_user": current_user if current_user is not None else get_current_user(request, db),
            "messages": pop_messages(request),
            "chain_ready": is_chain_ready(),
        }
    )
    return templates.TemplateResponse(template_name, payload)


def redirect_with_message(request: Request, url: str, category: str, text: str) -> RedirectResponse:
    flash(request, category, text)
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def poll_status_from_model(poll: Poll) -> str:
    now = now_utc()
    if now < poll.starts_at:
        return "pending"
    if now <= poll.ends_at:
        return "active"
    return "ended"


def base_poll_query() -> Select[tuple[Poll]]:
    return (
        select(Poll)
        .options(selectinload(Poll.creator), selectinload(Poll.votes).selectinload(PollVote.voter))
        .order_by(Poll.created_at.desc())
    )


def load_poll(db: Session, poll_id: int) -> Poll | None:
    return db.scalar(base_poll_query().where(Poll.id == poll_id))


def find_user_by_wallet(db: Session, wallet_address: str) -> User | None:
    return db.scalar(select(User).where(User.wallet_address == wallet_address.lower()))


def resolve_allowed_users(db: Session, raw_usernames: str) -> list[User]:
    usernames = [normalize_username(item) for item in parse_collection(raw_usernames)]
    if not usernames:
        raise ValueError("至少要填写一个允许投票的用户名。")

    users = db.scalars(select(User).where(User.username.in_(usernames)).order_by(User.username.asc())).all()
    found = {user.username for user in users}
    missing = [username for username in usernames if username not in found]
    if missing:
        raise ValueError(f"以下用户还没有注册：{', '.join(missing)}")

    users_by_name = {user.username: user for user in users}
    ordered_users = [users_by_name[username] for username in usernames]

    missing_wallets = [user.username for user in ordered_users if not user.wallet_address]
    if missing_wallets:
        raise ValueError(f"以下用户还没有绑定钱包地址：{', '.join(missing_wallets)}")

    wallets = [user.wallet_address for user in ordered_users if user.wallet_address]
    if len(wallets) != len(set(wallets)):
        raise ValueError("允许名单中存在重复钱包地址，请检查用户绑定。")

    return ordered_users


def validate_poll_form(
    db: Session,
    topic: str,
    starts_at_raw: str,
    ends_at_raw: str,
    options_raw: str,
    allowed_users_raw: str,
) -> dict:
    cleaned_topic = topic.strip()
    if len(cleaned_topic) < 3:
        raise ValueError("投票议题至少需要 3 个字符。")

    starts_at = parse_datetime_field(starts_at_raw, "开始时间")
    ends_at = parse_datetime_field(ends_at_raw, "结束时间")
    if starts_at >= ends_at:
        raise ValueError("结束时间必须晚于开始时间。")

    options = parse_collection(options_raw)
    if len(options) < 2:
        raise ValueError("候选项目至少要有 2 个。")

    allowed_users = resolve_allowed_users(db, allowed_users_raw)
    return {
        "topic": cleaned_topic,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "options": options,
        "allowed_users": allowed_users,
    }


def get_poll_form_defaults(poll: Poll | None = None, allowed_users: list[User] | None = None) -> dict[str, str]:
    if not poll:
        return {
            "topic": "",
            "starts_at": "",
            "ends_at": "",
            "options_raw": "",
            "allowed_users_raw": "",
        }

    return {
        "topic": poll.topic,
        "starts_at": utc_naive_to_local(poll.starts_at).strftime("%Y-%m-%dT%H:%M"),
        "ends_at": utc_naive_to_local(poll.ends_at).strftime("%Y-%m-%dT%H:%M"),
        "options_raw": "\n".join(poll.get_options()),
        "allowed_users_raw": "\n".join(user.username for user in (allowed_users or [])),
    }


def is_poll_mutable(poll: Poll) -> bool:
    return poll_status_from_model(poll) == "pending" and len(poll.votes) == 0


def build_poll_card(poll: Poll, current_user: User | None) -> dict:
    return {
        "id": poll.id,
        "topic": poll.topic,
        "status": poll_status_from_model(poll),
        "starts_at": poll.starts_at,
        "ends_at": poll.ends_at,
        "creator_username": poll.creator.username if poll.creator else "",
        "allowed_count": len(poll.get_allowed_user_ids()),
        "cached_participants": len(poll.votes),
        "chain_contract_address": poll.chain_contract_address,
        "chain_network_name": poll.chain_network_name or "sepolia",
        "contract_url": build_address_url(poll.chain_contract_address, poll.chain_chain_id, poll.chain_network_name),
        "chain_error": poll.chain_error,
        "can_manage": bool(current_user and poll.created_by_user_id == current_user.id),
        "can_access": bool(
            current_user
            and (poll.created_by_user_id == current_user.id or current_user.id in poll.get_allowed_user_ids())
        ) or poll_status_from_model(poll) == "ended",
    }


def is_live_poll_available_to_user(poll: Poll, current_user: User | None) -> bool:
    if current_user is None:
        return False
    if poll_status_from_model(poll) == "ended":
        return False
    return poll.created_by_user_id == current_user.id or current_user.id in poll.get_allowed_user_ids()


def require_login(request: Request, db: Session) -> User | RedirectResponse:
    user = get_current_user(request, db)
    if not user:
        return redirect_with_message(request, "/login", "error", "请先登录后再继续。")
    return user


def save_synced_action(db: Session, poll: Poll, user: User, action_type: str, tx_hash: str, candidate_id: int | None) -> None:
    existing_vote = db.scalar(select(PollVote).where(PollVote.poll_id == poll.id, PollVote.voter_id == user.id))
    if existing_vote:
        existing_vote.abstained = action_type == "abstain"
        existing_vote.selected_option_index = candidate_id if action_type == "vote" else None
        existing_vote.chain_tx_hash = tx_hash
        db.add(existing_vote)
        db.commit()
        return

    vote = PollVote(
        poll_id=poll.id,
        voter_id=user.id,
        abstained=action_type == "abstain",
        selected_option_index=candidate_id if action_type == "vote" else None,
        chain_tx_hash=tx_hash,
    )
    db.add(vote)
    db.commit()


def verify_chain_sync_payload(
    poll: Poll,
    user: User,
    action_type: str,
    tx_hash: str,
    candidate_id: str,
) -> dict[str, str | int | None]:
    if action_type not in {"vote", "abstain"}:
        raise ValueError("无效的链上回执同步类型。")
    if not poll.chain_contract_address:
        raise ValueError("这个投票还没有可同步的链上合约地址。")
    if not user.wallet_address:
        raise ValueError("请先在个人资料中绑定钱包地址，再同步链上交易。")

    normalized_tx_hash = tx_hash.strip()
    if not TX_HASH_PATTERN.match(normalized_tx_hash):
        raise ValueError("交易哈希格式不正确。")

    submitted_candidate_id: int | None = None
    if action_type == "vote":
        if not candidate_id.strip():
            raise ValueError("缺少候选项编号，无法同步投票记录。")
        try:
            submitted_candidate_id = int(candidate_id)
        except ValueError as exc:
            raise ValueError("候选项编号格式不正确。") from exc
    elif candidate_id.strip():
        raise ValueError("弃权同步不应提交候选项编号。")

    chain_action = fetch_voter_action(
        contract_address=poll.chain_contract_address,
        voter_address=user.wallet_address,
        from_block=poll.chain_deploy_block,
    )

    chain_action_type = chain_action.get("actionType")
    if chain_action_type not in {"vote", "abstain"}:
        raise ValueError("链上还没有找到这个钱包的有效投票记录。")
    if chain_action_type != action_type:
        raise ValueError("提交的同步类型与链上记录不一致。")

    chain_tx_hash = str(chain_action.get("txHash") or "").strip()
    if not TX_HASH_PATTERN.match(chain_tx_hash):
        raise ValueError("链上返回的交易哈希无效，暂时无法同步。")
    if chain_tx_hash.lower() != normalized_tx_hash.lower():
        raise ValueError("提交的交易哈希与链上记录不一致。")

    verified_candidate_id: int | None = None
    if action_type == "vote":
        raw_chain_candidate_id = chain_action.get("candidateId")
        try:
            verified_candidate_id = int(raw_chain_candidate_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("链上返回的候选项编号无效，暂时无法同步。") from exc

        if verified_candidate_id < 0 or verified_candidate_id >= len(poll.get_options()):
            raise ValueError("链上返回的候选项编号超出范围，暂时无法同步。")
        if submitted_candidate_id != verified_candidate_id:
            raise ValueError("提交的候选项编号与链上记录不一致。")

    return {
        "action_type": chain_action_type,
        "tx_hash": chain_tx_hash,
        "candidate_id": verified_candidate_id,
    }


def get_poll_mutation_error_message(poll: Poll) -> str:
    if poll_status_from_model(poll) != "pending":
        return "投票已经开始或结束，不能再修改或删除。"
    return "已经有人同步过链上交易，不能再修改或删除。"


def get_deployment_feedback(deployment: dict) -> tuple[str, str]:
    if deployment.get("deploymentStatus") == "PENDING":
        tx_hash = deployment.get("deployTxHash")
        if tx_hash:
            return (
                "success",
                f"部署交易已经广播到链上，正在等待区块确认。你可以先打开部署交易查看进度：{tx_hash}",
            )
        return ("success", "部署交易已经广播到链上，正在等待区块确认。")

    return ("success", "投票已经部署到链上，允许名单中的用户现在可以用钱包投票。")


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    current_user = get_current_user(request, db)
    polls = db.scalars(base_poll_query()).all()
    public_results = [build_poll_card(poll, current_user) for poll in polls if poll_status_from_model(poll) == "ended"]
    live_polls = [
        build_poll_card(poll, current_user)
        for poll in polls
        if is_live_poll_available_to_user(poll, current_user)
    ]

    return render_page(
        request,
        db,
        "index.html",
        {
            "public_results": public_results[:8],
            "accessible_live_polls": live_polls[:8],
        },
        current_user=current_user,
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    current_user = get_current_user(request, db)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return render_page(request, db, "register.html")


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    wallet_address: str = Form(...),
    db: Session = Depends(get_db),
):
    normalized_username = normalize_username(username)
    try:
        normalized_wallet = normalize_wallet_address(wallet_address)
    except ValueError as exc:
        return render_page(
            request,
            db,
            "register.html",
            {"form_error": str(exc), "prefill_username": normalized_username, "prefill_wallet_address": wallet_address},
        )

    if not USERNAME_PATTERN.match(normalized_username):
        return render_page(
            request,
            db,
            "register.html",
            {
                "form_error": "用户名只支持小写字母、数字、点、下划线、横线，长度 3 到 32 位。",
                "prefill_username": normalized_username,
                "prefill_wallet_address": normalized_wallet,
            },
        )

    if len(password) < 6:
        return render_page(
            request,
            db,
            "register.html",
            {
                "form_error": "密码至少需要 6 位。",
                "prefill_username": normalized_username,
                "prefill_wallet_address": normalized_wallet,
            },
        )

    if db.scalar(select(User).where(User.username == normalized_username)):
        return render_page(
            request,
            db,
            "register.html",
            {
                "form_error": "这个用户名已经存在。",
                "prefill_username": normalized_username,
                "prefill_wallet_address": normalized_wallet,
            },
        )

    if db.scalar(select(User).where(User.wallet_address == normalized_wallet)):
        return render_page(
            request,
            db,
            "register.html",
            {
                "form_error": "这个钱包地址已经绑定过其他账号。",
                "prefill_username": normalized_username,
                "prefill_wallet_address": normalized_wallet,
            },
        )

    user = User(username=normalized_username, password_hash=hash_password(password), wallet_address=normalized_wallet)
    db.add(user)
    db.commit()
    request.session["user_id"] = user.id
    flash(request, "success", "注册成功。你的账户已经绑定了链上钱包。")
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    current_user = get_current_user(request, db)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return render_page(request, db, "login.html")


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    normalized_username = normalize_username(username)
    user = db.scalar(select(User).where(User.username == normalized_username))
    if not user or not verify_password(password, user.password_hash):
        return render_page(
            request,
            db,
            "login.html",
            {"form_error": "用户名或密码不正确。", "prefill_username": normalized_username},
        )

    request.session["user_id"] = user.id
    flash(request, "success", "登录成功。")
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_db)):
    current_user = require_login(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    return render_page(request, db, "profile.html", current_user=current_user)


@app.post("/profile")
def update_profile(
    request: Request,
    wallet_address: str = Form(...),
    db: Session = Depends(get_db),
):
    current_user = require_login(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    try:
        normalized_wallet = normalize_wallet_address(wallet_address)
    except ValueError as exc:
        return render_page(
            request,
            db,
            "profile.html",
            {"form_error": str(exc)},
            current_user=current_user,
        )

    existing_user = db.scalar(select(User).where(User.wallet_address == normalized_wallet, User.id != current_user.id))
    if existing_user:
        return render_page(
            request,
            db,
            "profile.html",
            {"form_error": "这个钱包地址已经被其他账号绑定。"},
            current_user=current_user,
        )

    current_user.wallet_address = normalized_wallet
    db.add(current_user)
    db.commit()
    return redirect_with_message(request, "/profile", "success", "钱包地址已更新。")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    current_user = require_login(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    polls = db.scalars(base_poll_query()).all()
    created_polls = [build_poll_card(poll, current_user) for poll in polls if poll.created_by_user_id == current_user.id]
    invited_polls = [
        build_poll_card(poll, current_user)
        for poll in polls
        if poll.created_by_user_id != current_user.id and is_live_poll_available_to_user(poll, current_user)
    ]
    public_results = [build_poll_card(poll, current_user) for poll in polls if poll_status_from_model(poll) == "ended"]

    return render_page(
        request,
        db,
        "dashboard.html",
        {
            "created_polls": created_polls,
            "invited_polls": invited_polls,
            "public_results": public_results[:8],
        },
        current_user=current_user,
    )


@app.get("/polls/new", response_class=HTMLResponse)
def create_poll_page(request: Request, db: Session = Depends(get_db)):
    current_user = require_login(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    users = db.scalars(select(User).order_by(User.username.asc())).all()
    return render_page(
        request,
        db,
        "poll_form.html",
        {
            "page_title": "发布链上投票",
            "submit_label": "发布并部署到链上",
            "form_data": get_poll_form_defaults(),
            "registered_users": users,
            "poll": None,
        },
        current_user=current_user,
    )


@app.post("/polls/new")
def create_poll(
    request: Request,
    topic: str = Form(...),
    starts_at: str = Form(...),
    ends_at: str = Form(...),
    options_raw: str = Form(...),
    allowed_users_raw: str = Form(...),
    db: Session = Depends(get_db),
):
    current_user = require_login(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    users = db.scalars(select(User).order_by(User.username.asc())).all()
    form_data = {
        "topic": topic,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "options_raw": options_raw,
        "allowed_users_raw": allowed_users_raw,
    }

    if not current_user.wallet_address:
        return render_page(
            request,
            db,
            "poll_form.html",
            {
                "page_title": "发布链上投票",
                "submit_label": "发布并部署到链上",
                "form_error": "请先在个人资料中绑定钱包地址，然后再发布链上投票。",
                "form_data": form_data,
                "registered_users": users,
                "poll": None,
            },
            current_user=current_user,
        )

    try:
        payload = validate_poll_form(db, topic, starts_at, ends_at, options_raw, allowed_users_raw)
        deployment = deploy_poll_contract(
            title=payload["topic"],
            candidate_names=payload["options"],
            starts_at=payload["starts_at"],
            ends_at=payload["ends_at"],
            voter_addresses=[user.wallet_address for user in payload["allowed_users"] if user.wallet_address],
        )
    except (ValueError, ChainServiceError) as exc:
        return render_page(
            request,
            db,
            "poll_form.html",
            {
                "page_title": "发布链上投票",
                "submit_label": "发布并部署到链上",
                "form_error": str(exc),
                "form_data": form_data,
                "registered_users": users,
                "poll": None,
            },
            current_user=current_user,
        )

    poll = Poll(
        topic=payload["topic"],
        starts_at=payload["starts_at"],
        ends_at=payload["ends_at"],
        created_by_user_id=current_user.id,
        chain_contract_address=deployment["contractAddress"],
        chain_deploy_tx_hash=deployment["deployTxHash"],
        chain_network_name=deployment["networkName"],
        chain_chain_id=deployment["chainId"],
        chain_deploy_block=deployment["deployBlock"],
        chain_deployed_at=naive_utc_now(),
    )
    poll.set_options(payload["options"])
    poll.set_allowed_user_ids([user.id for user in payload["allowed_users"]])

    db.add(poll)
    db.commit()
    flash_category, flash_text = get_deployment_feedback(deployment)
    flash(request, flash_category, flash_text)
    return RedirectResponse(url=f"/polls/{poll.id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/polls/{poll_id}/edit", response_class=HTMLResponse)
def edit_poll_page(poll_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = require_login(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    poll = load_poll(db, poll_id)
    if not poll:
        return redirect_with_message(request, "/dashboard", "error", "这个投票不存在。")
    if poll.created_by_user_id != current_user.id:
        return redirect_with_message(request, "/dashboard", "error", "只有创建者才能修改投票。")
    if not is_poll_mutable(poll):
        return redirect_with_message(request, f"/polls/{poll_id}", "error", get_poll_mutation_error_message(poll))

    users = db.scalars(select(User).order_by(User.username.asc())).all()
    allowed_users = [user for user in users if user.id in set(poll.get_allowed_user_ids())]
    return render_page(
        request,
        db,
        "poll_form.html",
        {
            "page_title": "修改链上投票",
            "submit_label": "重新部署链上版本",
            "form_data": get_poll_form_defaults(poll, allowed_users),
            "registered_users": users,
            "poll": poll,
        },
        current_user=current_user,
    )


@app.post("/polls/{poll_id}/edit")
def edit_poll(
    poll_id: int,
    request: Request,
    topic: str = Form(...),
    starts_at: str = Form(...),
    ends_at: str = Form(...),
    options_raw: str = Form(...),
    allowed_users_raw: str = Form(...),
    db: Session = Depends(get_db),
):
    current_user = require_login(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    poll = load_poll(db, poll_id)
    if not poll:
        return redirect_with_message(request, "/dashboard", "error", "这个投票不存在。")
    if poll.created_by_user_id != current_user.id:
        return redirect_with_message(request, "/dashboard", "error", "只有创建者才能修改投票。")
    if not is_poll_mutable(poll):
        return redirect_with_message(request, f"/polls/{poll_id}", "error", get_poll_mutation_error_message(poll))

    users = db.scalars(select(User).order_by(User.username.asc())).all()
    form_data = {
        "topic": topic,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "options_raw": options_raw,
        "allowed_users_raw": allowed_users_raw,
    }

    try:
        payload = validate_poll_form(db, topic, starts_at, ends_at, options_raw, allowed_users_raw)
        deployment = deploy_poll_contract(
            title=payload["topic"],
            candidate_names=payload["options"],
            starts_at=payload["starts_at"],
            ends_at=payload["ends_at"],
            voter_addresses=[user.wallet_address for user in payload["allowed_users"] if user.wallet_address],
        )
    except (ValueError, ChainServiceError) as exc:
        return render_page(
            request,
            db,
            "poll_form.html",
            {
                "page_title": "修改链上投票",
                "submit_label": "重新部署链上版本",
                "form_error": str(exc),
                "form_data": form_data,
                "registered_users": users,
                "poll": poll,
            },
            current_user=current_user,
        )

    poll.topic = payload["topic"]
    poll.starts_at = payload["starts_at"]
    poll.ends_at = payload["ends_at"]
    poll.chain_contract_address = deployment["contractAddress"]
    poll.chain_deploy_tx_hash = deployment["deployTxHash"]
    poll.chain_network_name = deployment["networkName"]
    poll.chain_chain_id = deployment["chainId"]
    poll.chain_deploy_block = deployment["deployBlock"]
    poll.chain_deployed_at = naive_utc_now()
    poll.chain_error = None
    poll.votes.clear()
    poll.set_options(payload["options"])
    poll.set_allowed_user_ids([user.id for user in payload["allowed_users"]])

    db.add(poll)
    db.commit()
    flash_category, flash_text = get_deployment_feedback(deployment)
    flash(
        request,
        flash_category,
        f"投票已经重新提交部署。旧合约仍然存在，但应用会以后新的合约地址为准。{flash_text}",
    )
    return RedirectResponse(url=f"/polls/{poll.id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/polls/{poll_id}/delete")
def delete_poll(poll_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = require_login(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    poll = load_poll(db, poll_id)
    if not poll:
        return redirect_with_message(request, "/dashboard", "error", "这个投票不存在。")
    if poll.created_by_user_id != current_user.id:
        return redirect_with_message(request, "/dashboard", "error", "只有创建者才能删除投票。")
    if not is_poll_mutable(poll):
        return redirect_with_message(request, f"/polls/{poll_id}", "error", get_poll_mutation_error_message(poll))

    db.delete(poll)
    db.commit()
    return redirect_with_message(
        request,
        "/dashboard",
        "success",
        "投票记录已从应用删除。注意：已经部署过的合约不会从区块链上消失。",
    )


@app.get("/polls/{poll_id}", response_class=HTMLResponse)
def poll_detail(poll_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    poll = load_poll(db, poll_id)
    if not poll:
        return redirect_with_message(request, "/", "error", "这个投票不存在。")

    allowed_user_ids = set(poll.get_allowed_user_ids())
    if poll_status_from_model(poll) != "ended":
        if not current_user:
            return redirect_with_message(request, "/login", "error", "请先登录后查看这个投票。")
        if current_user.id not in allowed_user_ids and current_user.id != poll.created_by_user_id:
            return redirect_with_message(request, "/dashboard", "error", "你不在这个投票的允许名单里。")

    allowed_users = db.scalars(select(User).where(User.id.in_(allowed_user_ids)).order_by(User.username.asc())).all()

    chain_summary = None
    viewer_action = {"actionType": None}
    chain_error = poll.chain_error

    if poll.chain_contract_address:
        try:
            chain_summary = fetch_contract_summary(
                contract_address=poll.chain_contract_address,
                viewer_address=current_user.wallet_address if current_user and current_user.wallet_address else None,
            )
            if current_user and current_user.wallet_address:
                viewer_action = fetch_voter_action(
                    contract_address=poll.chain_contract_address,
                    voter_address=current_user.wallet_address,
                    from_block=poll.chain_deploy_block,
                )
        except ChainServiceError as exc:
            chain_error = str(exc)

    return render_page(
        request,
        db,
        "poll_detail.html" if poll_status_from_model(poll) != "ended" else "poll_results.html",
        {
            "poll": poll,
            "poll_status": poll_status_from_model(poll),
            "allowed_users": allowed_users,
            "chain_summary": chain_summary,
            "viewer_action": viewer_action,
            "chain_error": chain_error,
            "contract_url": build_address_url(poll.chain_contract_address, poll.chain_chain_id, poll.chain_network_name),
            "deploy_tx_url": build_tx_url(poll.chain_deploy_tx_hash, poll.chain_chain_id, poll.chain_network_name),
        },
        current_user=current_user,
    )


@app.get("/polls/{poll_id}/results", response_class=HTMLResponse)
def poll_results_page(poll_id: int, request: Request, db: Session = Depends(get_db)):
    poll = load_poll(db, poll_id)
    current_user = get_current_user(request, db)
    if not poll:
        return redirect_with_message(request, "/", "error", "这个投票不存在。")
    if poll_status_from_model(poll) != "ended":
        return redirect_with_message(request, f"/polls/{poll_id}", "error", "投票尚未结束，结果页还不能公开。")

    chain_summary = None
    chain_error = poll.chain_error
    if poll.chain_contract_address:
        try:
            chain_summary = fetch_contract_summary(poll.chain_contract_address)
        except ChainServiceError as exc:
            chain_error = str(exc)

    return render_page(
        request,
        db,
        "poll_results.html",
        {
            "poll": poll,
            "poll_status": poll_status_from_model(poll),
            "chain_summary": chain_summary,
            "chain_error": chain_error,
            "contract_url": build_address_url(poll.chain_contract_address, poll.chain_chain_id, poll.chain_network_name),
            "deploy_tx_url": build_tx_url(poll.chain_deploy_tx_hash, poll.chain_chain_id, poll.chain_network_name),
        },
        current_user=current_user,
    )


@app.post("/polls/{poll_id}/sync-chain-action")
def sync_chain_action(
    poll_id: int,
    request: Request,
    action_type: str = Form(...),
    tx_hash: str = Form(...),
    candidate_id: str = Form(""),
    db: Session = Depends(get_db),
):
    current_user = require_login(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    poll = load_poll(db, poll_id)
    if not poll:
        return redirect_with_message(request, "/dashboard", "error", "这个投票不存在。")
    if current_user.id not in poll.get_allowed_user_ids():
        return redirect_with_message(request, "/dashboard", "error", "你不在这个投票的允许名单里。")
    try:
        verified_payload = verify_chain_sync_payload(
            poll=poll,
            user=current_user,
            action_type=action_type,
            tx_hash=tx_hash,
            candidate_id=candidate_id,
        )
    except (ValueError, ChainServiceError) as exc:
        return redirect_with_message(request, f"/polls/{poll_id}", "error", str(exc))

    save_synced_action(
        db,
        poll,
        current_user,
        str(verified_payload["action_type"]),
        str(verified_payload["tx_hash"]),
        verified_payload["candidate_id"] if isinstance(verified_payload["candidate_id"], int) else None,
    )
    return redirect_with_message(request, f"/polls/{poll_id}", "success", "链上交易已经同步到应用。")


@app.post("/polls/{poll_id}/vote")
def vote_redirect(poll_id: int) -> RedirectResponse:
    return RedirectResponse(url=f"/polls/{poll_id}", status_code=status.HTTP_303_SEE_OTHER)
