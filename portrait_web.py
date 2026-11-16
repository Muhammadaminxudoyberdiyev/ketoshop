"""
Admin sayti — «🧑‍🤝‍🧑 Mijozlar» tabi: bot AI si bilan gaplashgan har bir
mijozning portreti. Faqat o'qish.

Egasi, 2026-11-16: "Dashboardda botning AI si bilan gaplashgan har bir
foydalanuvchining mijoz portretini ko'rish imkonini qo'sh."

Manbalar (hech biri o'zgartirilmaydi):
  * ai_conversations (ai_stats.py) — kim, qachon, nechta suhbat, mavzular.
    Faqat bot va sayt kanallari: guruhdagi javoblar mijoz bilan suhbat emas.
  * customer_portrait (customer_portrait.py) — murojaat ismi, yosh, jins
    (manbasi va ishonchi bilan), maqsadlar.
  * ai_customer_notes (ai_memory.py) — qiziqish, fikr, eslatma.
  * orders / users — buyurtmalar soni va summasi «Qayta sotuv» tabidagi
    asosda (database.SALE_SQL, qo'lda va B2B siz), Keto balansi.

MAXFIYLIK
  * /malumotlarim orqali ma'lumotini o'chirgan mijoz (opted_out_at): portret,
    suhbat mavzulari va AI eslatmalari umuman qaytarilmaydi — server o'zi
    tashlaydi, sahifa faqat "ma'lumot o'chirilgan" deb ko'rsatadi. Telegram
    ismi va buyurtmalar — do'kon hisobi, qoladi (/malumotlarim matnidagidek).
  * Adminlar va ichki akkauntlar (LEADERBOARD_EXCLUDED_USER_IDS) na ro'yxatda,
    na kartada — kunlik portret hisoboti bilan bir xil ro'yxat.
"""
import json
import math

import ai_memory
import ai_stats
import customer_portrait
import database

CHANNELS = ["bot", "site"]
PER_PAGE = 30
FILTERS = ("all", "portrait", "no_portrait", "orders")
TOPICS_SHOWN = 3
NOTE_KINDS = ("interest", "feedback", "note")
NOTES_SHOWN = 60
RECENT_ORDERS = 5
SEARCH_MAX = 64
_MAX_BIGINT = 2 ** 63 - 1

# Kunlik hisobotdagi "portreti bor" bilan bir xil: kamida bitta maydon bor va
# mijoz o'chirmagan. COALESCE — portret qatori yo'q mijoz NULL emas, FALSE
# bo'lsin ("Portretsiz" filtri NOT bilan ishlaydi).
_HAS_PORTRAIT = ("COALESCE(p.opted_out_at IS NULL AND (p.display_name IS NOT NULL OR p.age IS NOT NULL "
                 "OR p.gender <> 'unknown' OR cardinality(p.goals) > 0), FALSE)")

_FILTER_SQL = {
    "all": "TRUE",
    "portrait": "has_portrait",
    "no_portrait": "NOT has_portrait",
    "orders": "orders > 0",
}


def _people_sql() -> str:
    """$1 — kanallar, $2 — chiqarib tashlanadigan ID lar. Har bir mijoz bitta
    qator: suhbatlar, Telegram ismi, portret va buyurtmalar yig'indisi."""
    return f"""
    WITH conv AS (
        SELECT user_id, MIN(started_at) AS first_ai_at, MAX(last_at) AS last_ai_at,
               COUNT(*) AS conversations, COALESCE(SUM(messages), 0) AS messages,
               array_agg(DISTINCT channel ORDER BY channel) AS channels
          FROM ai_conversations
         WHERE channel = ANY($1::text[]) AND user_id <> ALL($2::bigint[])
         GROUP BY user_id
    ), ord AS (
        SELECT o.user_id, COUNT(*) AS orders, COALESCE(SUM(o.total), 0) AS spent,
               MAX(o.created_at) AS last_order_at
          FROM orders o
         WHERE o.user_id IN (SELECT user_id FROM conv)
           AND {database.sale_sql('o')} AND {database._REAL_ORDER}
         GROUP BY o.user_id
    ), people AS (
        SELECT conv.*, u.full_name, u.username,
               p.display_name, p.age, p.age_group, p.gender, p.gender_source,
               p.gender_confidence, p.goals,
               (p.opted_out_at IS NOT NULL) AS opted_out,
               {_HAS_PORTRAIT} AS has_portrait,
               COALESCE(ord.orders, 0) AS orders, COALESCE(ord.spent, 0) AS spent,
               ord.last_order_at
          FROM conv
          LEFT JOIN users u ON u.user_id = conv.user_id
          LEFT JOIN customer_portrait p ON p.user_id = conv.user_id
          LEFT JOIN ord ON ord.user_id = conv.user_id
    )"""


# $3 — aniq ID (faqat raqam yozilganda), $4 — ILIKE namunasi ('' — qidiruvsiz).
# O'chirgan mijozning murojaat ismi bo'yicha qidirilmaydi.
_SEARCH_SQL = """($4 = '' OR user_id::text = $3 OR full_name ILIKE $4 OR username ILIKE $4
                  OR (NOT opted_out AND display_name ILIKE $4))"""

_STATS_SQL = """
    SELECT COUNT(*) AS talked,
           COUNT(*) FILTER (WHERE has_portrait) AS portraits,
           COUNT(*) FILTER (WHERE NOT opted_out AND display_name IS NOT NULL) AS with_name,
           COUNT(*) FILTER (WHERE NOT opted_out AND age IS NOT NULL) AS with_age,
           COUNT(*) FILTER (WHERE NOT opted_out AND gender = 'f') AS female,
           COUNT(*) FILTER (WHERE NOT opted_out AND gender = 'm') AS male,
           COUNT(*) FILTER (WHERE NOT opted_out AND cardinality(goals) > 0) AS with_goals,
           COUNT(*) FILTER (WHERE opted_out) AS opted_out,
           COUNT(*) FILTER (WHERE orders > 0) AS with_orders
      FROM people"""

_GOALS_SQL = """
    SELECT g AS goal, COUNT(*) AS n
      FROM people, unnest(goals) AS g
     WHERE NOT opted_out
     GROUP BY g ORDER BY n DESC, g"""

_TOPICS_SQL = """
    SELECT c.user_id, t AS topic, COUNT(*) AS n
      FROM ai_conversations c, unnest(c.topics) AS t
     WHERE c.channel = ANY($1::text[]) AND c.user_id = ANY($2::bigint[])
     GROUP BY c.user_id, t
     ORDER BY c.user_id, n DESC, t"""


def excluded_ids() -> list[int]:
    """Adminlar va ichki akkauntlar — kunlik portret hisobotidagi ro'yxat."""
    return customer_portrait._excluded_ids()


def _like(text: str) -> str:
    text = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{text}%"


def search_args(q) -> tuple[str, str, str]:
    """(tozalangan so'rov, aniq ID, ILIKE namunasi). '@ism' — username."""
    q = " ".join(str(q or "").split())[:SEARCH_MAX]
    bare = q.lstrip("@").strip()
    exact_id = bare if bare.isdigit() else ""
    return q, exact_id, (_like(bare) if bare else "")


def _topics(rows) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for r in rows:
        items = out.setdefault(int(r["user_id"]), [])
        if len(items) < TOPICS_SHOWN:
            key = r["topic"]
            items.append({"key": key, "title": ai_stats.TOPIC_TITLES.get(key, key), "n": int(r["n"])})
    return out


def person(row: dict, topics: list[dict] | None = None) -> dict:
    """Bitta mijoz qatori (API shakli). O'chirgan mijozda portret, mavzular
    bo'sh — bazada nima qolgan bo'lsa ham."""
    opted = bool(row.get("opted_out"))
    out = {
        "user_id": int(row["user_id"]),
        "full_name": (row.get("full_name") or "").strip(),
        "username": row.get("username") or "",
        "opted_out": opted,
        "has_portrait": bool(row.get("has_portrait")) and not opted,
        "display_name": None, "age": None, "age_group": None,
        "gender": "unknown", "gender_source": None, "gender_confidence": None,
        "goals": [], "goal_labels": [],
        "first_ai_at": row.get("first_ai_at"), "last_ai_at": row.get("last_ai_at"),
        "conversations": int(row.get("conversations") or 0),
        "messages": int(row.get("messages") or 0),
        "channels": list(row.get("channels") or []),
        "topics": [] if opted else list(topics or []),
        "orders": int(row.get("orders") or 0),
        "spent": float(row.get("spent") or 0),
        "last_order_at": row.get("last_order_at"),
    }
    if opted:
        return out
    age = row.get("age")
    goals = list(row.get("goals") or [])
    confidence = row.get("gender_confidence")
    out.update(
        display_name=row.get("display_name") or None,
        age=int(age) if age is not None else None,
        age_group=(row.get("age_group") or customer_portrait.age_group(int(age))) if age is not None else None,
        gender=row.get("gender") or "unknown",
        gender_source=row.get("gender_source"),
        gender_confidence=round(float(confidence), 2) if confidence is not None else None,
        goals=goals,
        goal_labels=customer_portrait.goal_labels(goals),
    )
    return out


async def _ensure(conn) -> None:
    # Deploydan keyin hali hech kim AI bilan gaplashmagan bo'lsa ham jadval bor.
    await ai_stats._ensure(conn)
    await customer_portrait._ensure(conn)


async def list_page(q: str = "", page: int = 1, flt: str = "all") -> dict:
    """GET /admin/api/portraits — hisoblagichlar va bitta sahifa (PER_PAGE),
    oxirgi AI suhbati yangisi oldin."""
    q, exact_id, pattern = search_args(q)
    flt = flt if flt in FILTERS else "all"
    page = max(1, min(int(page or 1), 100000))
    excluded = excluded_ids()
    where = f"({_FILTER_SQL[flt]}) AND {_SEARCH_SQL}"
    base = _people_sql()
    async with database.pool.acquire() as conn:
        await _ensure(conn)
        stats = dict(await conn.fetchrow(base + _STATS_SQL, CHANNELS, excluded))
        goals = [dict(r) for r in await conn.fetch(base + _GOALS_SQL, CHANNELS, excluded)]
        total = int(await conn.fetchval(
            base + f" SELECT COUNT(*) FROM people WHERE {where}",
            CHANNELS, excluded, exact_id, pattern) or 0)
        rows = [dict(r) for r in await conn.fetch(
            base + f""" SELECT * FROM people WHERE {where}
                        ORDER BY last_ai_at DESC, user_id DESC LIMIT $5 OFFSET $6""",
            CHANNELS, excluded, exact_id, pattern, PER_PAGE, (page - 1) * PER_PAGE)]
        open_ids = [int(r["user_id"]) for r in rows if not r.get("opted_out")]
        topics = _topics(await conn.fetch(_TOPICS_SQL, CHANNELS, open_ids)) if open_ids else {}
    return {
        "stats": {k: int(v or 0) for k, v in stats.items()},
        "goals": [{"goal": g["goal"], "label": (customer_portrait.goal_labels([g["goal"]]) or [g["goal"]])[0],
                   "n": int(g["n"])} for g in goals],
        "rows": [person(r, topics.get(int(r["user_id"]))) for r in rows],
        "total": total,
        "page": page,
        "pages": max(1, math.ceil(total / PER_PAGE)),
        "per_page": PER_PAGE,
        "filter": flt,
        "q": q,
    }


def _order(order: dict) -> dict:
    raw = order.get("items")
    try:
        items = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except (TypeError, ValueError):
        items = []
    lines = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        lines.append({
            "name": str(item.get("name") or "—"),
            "quantity": item.get("quantity"),
            "unit": item.get("unit") or "",
            "price": item.get("price"),
            "gift": bool(item.get("is_bonus") or item.get("is_gift")),
        })
    return {
        "id": order.get("id"),
        "created_at": order.get("created_at"),
        "status": order.get("status") or "",
        "total": float(order.get("total") or 0),
        "delivery_method": order.get("delivery_method") or "",
        "items": lines,
    }


def _note(note: dict) -> dict:
    return {"kind": note["kind"], "text": note.get("text") or "", "created_at": note.get("created_at")}


async def card(user_id: int) -> dict | None:
    """GET /admin/api/portraits/{user_id} — to'liq karta yoki None (AI bilan
    gaplashmagan, admin / ichki akkaunt)."""
    excluded = excluded_ids()
    if user_id in excluded or not 0 < user_id <= _MAX_BIGINT:
        return None
    async with database.pool.acquire() as conn:
        await _ensure(conn)
        row = await conn.fetchrow(_people_sql() + " SELECT * FROM people WHERE user_id = $3",
                                  CHANNELS, excluded, user_id)
        if row is None:
            return None
        row = dict(row)
        opted = bool(row.get("opted_out"))
        topics = [] if opted else _topics(await conn.fetch(_TOPICS_SQL, CHANNELS, [user_id])).get(user_id, [])
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    user = dict(user) if user else {}
    out = person(row, topics)
    notes = []
    if not opted:
        notes = [_note(n) for n in await ai_memory.notes(user_id) if n.get("kind") in NOTE_KINDS]
        notes = list(reversed(notes[-NOTES_SHOWN:]))          # yangisi oldin
    orders = [o for o in await database.get_user_orders(user_id)
              if (o.get("source") or "bot") not in ("manual", "b2b")]
    username = out["username"]
    out.update(
        language=user.get("language") or "",
        joined_at=user.get("created_at"),
        keto_balance=int(user.get("keto_balance") or 0),
        keto_lifetime=int(user.get("keto_lifetime") or 0),
        tg_link=f"tg://user?id={user_id}",
        tme_link=f"https://t.me/{username}" if username else "",
        notes=notes,
        recent_orders=[_order(o) for o in orders[:RECENT_ORDERS]],
    )
    return out
