"""Simulated street clock, hour-by-hour replay, and demo persona automation."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.agents.graph import ClaimGraphRunner
from app.agents.nodes import load_street_histories, run_batch_payback
from app.config import API_ROOT
from app.db import DEFAULT_STREET_ID
from app.detector.baseline import compute_baseline_paise
from app.models import IST, Ask, Detection, PaymentHourly, Refund, Shop, now_ist, to_ist

logger = logging.getLogger(__name__)

SAMPLES_DIR: Path = API_ROOT / "samples"
SELVI_SHOP_ID: str = "shop_01"
AUTO_VOICE_PERSONAS: dict[str, str] = {
    "shop_10": "tts_leave.wav",
    "shop_12": "tts_qr_switch.wav",
}


@dataclass
class ScenarioSnapshot:
    """Read-only summary of the simulated scenario clock and display statuses."""

    running: bool
    active_day: str | None
    current_hour: str | None
    speed: float
    hours_completed: int
    shop_statuses: dict[str, str]


@dataclass
class ScenarioRunner:
    """Replays simulated street hours, triggers end-of-day decide(), and runs demo personas."""

    graph_runner: ClaimGraphRunner
    samples_dir: Path = SAMPLES_DIR
    street_id: str = DEFAULT_STREET_ID
    running: bool = False
    active_day: date | None = None
    current_hour: datetime | None = None
    speed: float = 60.0
    hours_completed: int = 0
    shop_statuses: dict[str, str] = field(default_factory=dict)
    _active_task: asyncio.Task[None] | None = None
    _persona_tasks: list[asyncio.Task[None]] = field(default_factory=list)
    _payback_tasks: dict[str, asyncio.Task[list[dict[str, Any]]]] = field(default_factory=dict)

    def _bus(self) -> Any:
        return self.graph_runner.runtime.bus

    def _db(self) -> Any:
        return self.graph_runner.runtime.db

    def snapshot(self) -> ScenarioSnapshot:
        """Return current clock and display-only shutter status snapshot."""
        return ScenarioSnapshot(
            running=self.running,
            active_day=self.active_day.isoformat() if self.active_day is not None else None,
            current_hour=self.current_hour.isoformat() if self.current_hour is not None else None,
            speed=self.speed,
            hours_completed=self.hours_completed,
            shop_statuses=dict(self.shop_statuses),
        )

    async def cancel_background(self) -> None:
        """Cancel any active replay or simulated persona tasks and wait for clean exit."""
        tasks: list[asyncio.Task[Any]] = []
        if self._active_task is not None and not self._active_task.done():
            self._active_task.cancel()
            tasks.append(self._active_task)
        for task in self._persona_tasks:
            if not task.done():
                task.cancel()
                tasks.append(task)
        for p_task in self._payback_tasks.values():
            if not p_task.done():
                p_task.cancel()
                tasks.append(p_task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._active_task = None
        self._persona_tasks.clear()
        self._payback_tasks.clear()
        self.running = False

    def start_batch_payback(self, batch_id: str) -> asyncio.Task[list[dict[str, Any]]]:
        """Start background payback task for an approved batch, returning immediately."""
        existing = self._payback_tasks.get(batch_id)
        if existing is not None and not existing.done():
            return existing
        task = asyncio.create_task(run_batch_payback(self.graph_runner.runtime, batch_id))
        self._payback_tasks[batch_id] = task
        return task

    async def wait_for_payback(self, batch_id: str | None = None) -> list[dict[str, Any]]:
        """Await completion of active payback task(s) (used in tests and synchronous checks)."""
        if batch_id is not None:
            task = self._payback_tasks.get(batch_id)
            if task is None:
                return []
            return await task
        if not self._payback_tasks:
            return []
        results = await asyncio.gather(*self._payback_tasks.values())
        merged: list[dict[str, Any]] = []
        for group in results:
            merged.extend(group)
        return merged

    async def reset(self) -> dict[str, int]:
        """Cancel active runs, clear detections/asks/claims, and re-seed from CSV."""
        await self.cancel_background()
        counts = await asyncio.to_thread(self._reset_sync)
        self.active_day = None
        self.current_hour = None
        self.hours_completed = 0
        self.running = False
        with self._db().session() as sess:
            shop_ids = list(
                sess.scalars(
                    select(Shop.id).where(Shop.street_id == self.street_id).order_by(Shop.id)
                )
            )
        self.shop_statuses = {sid: "trading" for sid in shop_ids}
        return counts

    def _reset_sync(self) -> dict[str, int]:
        self.graph_runner.reset()
        return self._db().seed(reset=True)

    async def start_run(self, day_val: date, *, speed: float = 60.0) -> dict[str, Any]:
        """Start or run synchronously (`speed <= 0`) the simulation for `day_val`."""
        await self.cancel_background()

        # Ensure a repeated /run without explicit /reset starts from clean run tables.
        def _needs_clean() -> bool:
            with self._db().session() as sess:
                count = sess.scalar(select(func.count(Detection.id))) or 0
                return count > 0

        if await asyncio.to_thread(_needs_clean):
            await asyncio.to_thread(self._reset_sync)

        self.active_day = day_val
        self.current_hour = None
        self.hours_completed = 0
        self.speed = float(speed)

        if speed <= 0:
            result = await self._execute_day(day_val, speed=0.0, run_personas_inline=True)
            return {
                "status": "completed",
                "day": day_val.isoformat(),
                "speed": speed,
                **result,
            }

        self.running = True
        self._active_task = asyncio.create_task(
            self._run_background(day_val, speed=float(speed)),
            name=f"scenario-run-{day_val.isoformat()}",
        )
        return {
            "status": "started",
            "day": day_val.isoformat(),
            "speed": speed,
        }

    async def _run_background(self, day_val: date, *, speed: float) -> None:
        try:
            await self._execute_day(day_val, speed=speed, run_personas_inline=False)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scenario background run failed for day=%s", day_val.isoformat())
            raise
        finally:
            self.running = False

    def _load_day_hours(
        self, day_val: date
    ) -> tuple[
        list[str],
        list[datetime],
        dict[tuple[str, datetime], tuple[int, int]],
        dict[str, set[int]],
    ]:
        """Load shop IDs, sorted IST hourly timestamps, payment counts, and normal trading hours."""
        day_start = datetime(day_val.year, day_val.month, day_val.day, tzinfo=IST)
        day_end = day_start + timedelta(days=1)

        with self._db().session() as sess:
            shop_ids = list(
                sess.scalars(
                    select(Shop.id).where(Shop.street_id == self.street_id).order_by(Shop.id)
                )
            )
            stmt = (
                select(
                    PaymentHourly.shop_id,
                    PaymentHourly.ts_hour,
                    PaymentHourly.n_payments,
                    PaymentHourly.amount_paise,
                )
                .where(
                    PaymentHourly.shop_id.in_(shop_ids),
                    PaymentHourly.ts_hour >= day_start,
                    PaymentHourly.ts_hour < day_end,
                )
                .order_by(PaymentHourly.ts_hour, PaymentHourly.shop_id)
            )
            hour_set: set[datetime] = set()
            hourly_map: dict[tuple[str, datetime], tuple[int, int]] = {}
            for sid, ts_hour, n_pay, amt in sess.execute(stmt):
                ts_ist = to_ist(ts_hour)
                hour_set.add(ts_ist)
                hourly_map[(sid, ts_ist)] = (int(n_pay), int(amt))

            hist_stmt = select(
                PaymentHourly.shop_id,
                PaymentHourly.ts_hour,
                PaymentHourly.n_payments,
            ).where(
                PaymentHourly.shop_id.in_(shop_ids),
                PaymentHourly.ts_hour < day_start,
            )
            active_days_by_shop: dict[str, set[date]] = {sid: set() for sid in shop_ids}
            hour_hits_by_shop: dict[str, dict[int, int]] = {
                sid: defaultdict(int) for sid in shop_ids
            }
            for sid, ts_hour, n_pay in sess.execute(hist_stmt):
                if int(n_pay) > 0:
                    ts_ist = to_ist(ts_hour)
                    active_days_by_shop[sid].add(ts_ist.date())
                    hour_hits_by_shop[sid][ts_ist.hour] += 1

            normal_hours: dict[str, set[int]] = {}
            for sid in shop_ids:
                n_days = len(active_days_by_shop[sid])
                if n_days < 2:
                    normal_hours[sid] = set(range(8, 22))
                    continue
                hrs = {
                    hr
                    for hr, hits in hour_hits_by_shop[sid].items()
                    if (hits / n_days) >= 0.50
                }
                normal_hours[sid] = hrs if hrs else set(range(8, 22))

        return shop_ids, sorted(hour_set), hourly_map, normal_hours

    async def _execute_day(
        self,
        day_val: date,
        *,
        speed: float,
        run_personas_inline: bool,
    ) -> dict[str, Any]:
        shop_ids, hours_ist, hourly_map, normal_hours = await asyncio.to_thread(
            self._load_day_hours, day_val
        )
        self.shop_statuses = {sid: "trading" for sid in shop_ids}

        last_active_hour: dict[str, datetime | None] = {sid: None for sid in shop_ids}
        for ts_hour in hours_ist:
            for sid in shop_ids:
                n_pay, amt = hourly_map.get((sid, ts_hour), (0, 0))
                if n_pay > 0 and amt > 0:
                    last_active_hour[sid] = ts_hour

        step_delay = 0.0 if speed <= 0 else (60.0 / speed)
        prev_display: dict[str, str] = {}

        # Replay each simulated hour for display-only shutter status (never feeds decide()).
        for ts_hour in hours_ist:
            self.current_hour = ts_hour
            self.hours_completed += 1
            self._bus().publish("clock.tick", {"ts": ts_hour.isoformat()})

            for sid in shop_ids:
                norm_hrs = normal_hours.get(sid, set(range(8, 22)))
                first_norm_hr = min(norm_hrs) if norm_hrs else 8
                last_norm_hr = max(norm_hrs) if norm_hrs else 21
                last_act = last_active_hour.get(sid)

                if last_act is None:
                    display_status = "quiet" if ts_hour.hour >= first_norm_hr else "trading"
                elif ts_hour <= last_act or last_act.hour >= min(last_norm_hr, 20):
                    display_status = "trading"
                else:
                    display_status = "quiet" if ts_hour.hour in norm_hrs else "trading"

                self.shop_statuses[sid] = display_status
                if prev_display.get(sid) != display_status:
                    prev_display[sid] = display_status
                    self._bus().publish("shop.status", {"shop_id": sid, "status": display_status})

            if step_delay > 0:
                await asyncio.sleep(step_delay)

        # End of simulated day (after 22:00): run deterministic decide() once per shop via LangGraph.
        run_tag = uuid.uuid4().hex[:8]
        day_iso = day_val.isoformat()
        pending_asks: list[tuple[str, str, str]] = []  # (ask_id, shop_id, ask_kind)

        for sid in shop_ids:
            thread_id = f"run_{run_tag}_{sid}"
            res = await asyncio.to_thread(
                self.graph_runner.run_shop_day,
                shop_id=sid,
                day_iso=day_iso,
                street_id=self.street_id,
                thread_id=thread_id,
            )
            det_info = res.get("detection", {})
            self.shop_statuses[sid] = "dropped" if det_info.get("dropped") else "trading"
            if res.get("__interrupt__"):
                intr = res["__interrupt__"][0]
                payload = intr.value if hasattr(intr, "value") else {}
                if isinstance(payload, dict) and payload.get("ask_id"):
                    pending_asks.append(
                        (
                            str(payload["ask_id"]),
                            str(payload["shop_id"]),
                            str(payload["ask_kind"]),
                        )
                    )

        # Trigger automated simulated personas sequentially so SQLite and MemorySaver never contend.
        persona_coros: list[tuple[float, str, str, str]] = []
        step_pause = 0.0 if (speed <= 0 or run_personas_inline) else min(0.25, max(0.05, 9.0 / speed))

        for ask_id, shop_id, ask_kind in pending_asks:
            if shop_id == SELVI_SHOP_ID and ask_kind == "consent":
                # Selvi's consent must come only from a real merchant tap.
                continue
            if ask_kind == "consent":
                persona_coros.append((step_pause, ask_id, shop_id, "consent"))
            elif ask_kind == "voice" and shop_id in AUTO_VOICE_PERSONAS:
                persona_coros.append((step_pause, ask_id, shop_id, "voice"))

        for delay, ask_id, shop_id, kind in persona_coros:
            await self._run_persona_action(delay, ask_id, shop_id, kind)

        return {
            "shops_evaluated": len(shop_ids),
            "pending_asks": len(pending_asks),
        }

    async def _run_persona_action(
        self,
        delay_seconds: float,
        ask_id: str,
        shop_id: str,
        kind: str,
    ) -> None:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        def _execute() -> None:
            with self._db().session() as sess:
                ask_row = sess.get(Ask, ask_id)
                if ask_row is None or ask_row.status != "pending":
                    return

            if kind == "consent":
                self.graph_runner.resume_consent(
                    ask_row,
                    answered_at=now_ist(),
                    simulated_label="Simulated consent",
                )
                return

            sample_name = AUTO_VOICE_PERSONAS.get(shop_id)
            if not sample_name:
                return
            sample_path = self.samples_dir / sample_name
            if not sample_path.exists():
                logger.warning("Missing sample voice file %s for %s", sample_path, shop_id)
                return
            audio_bytes = sample_path.read_bytes()
            self.graph_runner.resume_voice(
                ask_row,
                audio_bytes=audio_bytes,
                filename=sample_name,
                content_type="audio/wav",
                answered_at=now_ist(),
                simulated_label="Simulated reply",
            )

        await asyncio.to_thread(_execute)

    def build_street_view(
        self, street_id: str, target_day: date | None = None
    ) -> dict[str, Any] | None:
        """Build JSON payload for GET /api/street/{id}."""
        day_val = target_day or self.active_day or date(2026, 10, 21)
        day_start = datetime(day_val.year, day_val.month, day_val.day, tzinfo=IST)
        if self.active_day == day_val and self.current_hour is not None:
            cutoff_hour = self.current_hour
        else:
            cutoff_hour = day_start + timedelta(hours=22)

        with self._db().session() as sess:
            from app.models import Claim, Street

            street = sess.get(Street, street_id)
            if street is None:
                return None

            shops = list(
                sess.scalars(select(Shop).where(Shop.street_id == street_id).order_by(Shop.id))
            )
            histories = load_street_histories(sess, street_id, day_val)

            hourly_rows = sess.execute(
                select(
                    PaymentHourly.shop_id,
                    PaymentHourly.ts_hour,
                    PaymentHourly.n_payments,
                    PaymentHourly.amount_paise,
                )
                .where(
                    PaymentHourly.shop_id.in_([s.id for s in shops]),
                    PaymentHourly.ts_hour >= day_start,
                    PaymentHourly.ts_hour <= cutoff_hour,
                )
                .order_by(PaymentHourly.shop_id, PaymentHourly.ts_hour)
            )
            hourly_by_shop: dict[str, list[dict[str, Any]]] = defaultdict(list)
            revealed_totals: dict[str, int] = defaultdict(int)
            for sid, ts_hour, n_pay, amt in hourly_rows:
                ts_ist = to_ist(ts_hour)
                amt_int = int(amt)
                revealed_totals[sid] += amt_int
                hourly_by_shop[sid].append(
                    {
                        "ts_hour": ts_ist.isoformat(),
                        "n_payments": int(n_pay),
                        "amount_paise": amt_int,
                    }
                )

            detections_by_shop = {
                d.shop_id: d
                for d in sess.scalars(select(Detection).where(Detection.day == day_val))
            }
            asks_by_shop: dict[str, Ask] = {}
            for a in sess.scalars(select(Ask).order_by(Ask.created_at.desc())):
                asks_by_shop.setdefault(a.shop_id, a)
            claims_by_shop: dict[str, Claim] = {}
            for c in sess.scalars(select(Claim).order_by(Claim.created_at.desc())):
                claims_by_shop.setdefault(c.shop_id, c)
            refunds_by_claim: dict[str, Refund] = {}
            for r in sess.scalars(select(Refund).order_by(Refund.created_at.desc())):
                refunds_by_claim.setdefault(r.claim_id, r)

        snap = self.snapshot()
        shop_items: list[dict[str, Any]] = []
        for s in shops:
            hist = histories.get(s.id)
            baseline_paise = compute_baseline_paise(hist, day_val) if hist else 0
            det = detections_by_shop.get(s.id)
            ask_obj = asks_by_shop.get(s.id)
            claim_obj = claims_by_shop.get(s.id)
            refund_obj = refunds_by_claim.get(claim_obj.id) if claim_obj is not None else None

            status = self.shop_statuses.get(s.id, "trading")
            if det is not None:
                status = "dropped" if det.dropped else "trading"

            shop_items.append(
                {
                    "shop_id": s.id,
                    "name": s.name,
                    "owner": s.owner,
                    "category": s.category,
                    "lat": s.lat,
                    "lon": s.lon,
                    "plan_active": s.plan_active,
                    "status": status,
                    "baseline_paise": baseline_paise,
                    "today_income_paise": (
                        revealed_totals.get(s.id, 0) if self.active_day == day_val else 0
                    ),
                    "hourly": hourly_by_shop.get(s.id, []) if self.active_day == day_val else [],
                    "detection": (
                        {
                            "id": det.id,
                            "day": det.day.isoformat(),
                            "baseline_paise": det.baseline_paise,
                            "day_income_paise": det.day_income_paise,
                            "dropped": det.dropped,
                            "eligible": det.eligible,
                            "quorum_share": det.quorum_share,
                            "rain_mm": det.rain_mm,
                            "rain_source": det.rain_source,
                            "decision": det.decision,
                            "reason": det.reason,
                            "rules_version": det.rules_version,
                        }
                        if det is not None
                        else None
                    ),
                    "ask": (
                        {
                            "id": ask_obj.id,
                            "ask_kind": ask_obj.ask_kind,
                            "status": ask_obj.status,
                            "prompt_text_ta": ask_obj.prompt_text_ta,
                            "has_audio": ask_obj.prompt_audio_path is not None,
                            "reply_type": ask_obj.reply_type,
                            "transcript": ask_obj.transcript,
                            "cause_label": ask_obj.cause_label,
                            "confidence": ask_obj.confidence,
                            "simulated_label": ask_obj.simulated_label,
                            "answered_at": (
                                ask_obj.answered_at.isoformat()
                                if ask_obj.answered_at is not None
                                else None
                            ),
                        }
                        if ask_obj is not None
                        else None
                    ),
                    "claim": (
                        {
                            "id": claim_obj.id,
                            "status": claim_obj.status,
                            "batch_id": claim_obj.batch_id,
                            "consent_at": (
                                claim_obj.consent_at.isoformat()
                                if claim_obj.consent_at is not None
                                else None
                            ),
                            "evidence_url": f"/api/evidence/{claim_obj.id}.pdf",
                            "refund": (
                                {
                                    "id": refund_obj.id,
                                    "refund_id": refund_obj.refund_id,
                                    "amount_paise": refund_obj.amount_paise,
                                    "status": refund_obj.status,
                                    "label": refund_obj.mode_label,
                                }
                                if refund_obj is not None
                                else None
                            ),
                        }
                        if claim_obj is not None
                        else None
                    ),
                }
            )

        return {
            "street": {
                "id": street.id,
                "name": street.name,
                "lat": street.lat,
                "lon": street.lon,
            },
            "clock": {
                "running": snap.running,
                "active_day": snap.active_day,
                "current_hour": snap.current_hour,
                "speed": snap.speed,
                "hours_completed": snap.hours_completed,
            },
            "shops": shop_items,
        }
