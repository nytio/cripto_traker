from __future__ import annotations

from datetime import date
import hashlib
import json
import logging
import os
from typing import Any

from sqlalchemy import bindparam, cast, select
from sqlalchemy.dialects.postgresql import JSONB

from ..models import ForecastModelRun

try:
    from darts.models import BlockRNNModel, RNNModel
except ImportError:  # pragma: no cover - optional dependency fallback
    BlockRNNModel = None
    RNNModel = None

logger = logging.getLogger(__name__)


def _normalize_config(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_config(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize_config(item) for item in value]
    return value


def _default_work_dir() -> str:
    return os.environ.get("DARTS_WORK_DIR", "/var/lib/app/darts")


def canonical_model_key(
    scope: str,
    model_family: str,
    cell_type: str,
    horizon_days: int,
    transform: str,
    hyperparams: dict[str, Any],
) -> tuple[str, str, str]:
    payload = {
        "scope": scope,
        "model_family": model_family,
        "cell_type": cell_type,
        "horizon_days": horizon_days,
        "transform": transform,
        "hyperparams": _normalize_config(hyperparams),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:8]
    scope_slug = "global" if scope == "global_shared" else "percrypto"
    family_slug = "blockrnn" if model_family == "BlockRNNModel" else "rnn"
    cell_slug = cell_type.lower()
    transform_slug = transform.replace("_", "")
    model_name = (
        f"crypto_{scope_slug}__{family_slug}__{cell_slug}"
        f"__h{horizon_days}__{transform_slug}__{digest}"
    )
    work_dir = _default_work_dir()
    artifact_path_pt = os.path.join(work_dir, "artifacts", f"{model_name}.pt")
    return model_name, work_dir, artifact_path_pt


def create_model_run(
    session,
    scope: str,
    model_family: str,
    cell_type: str,
    horizon_days: int,
    transform: str,
    hyperparams_json: dict[str, Any],
    training_crypto_ids: list[int],
    train_start_date: date | None,
    train_end_date: date | None,
    cutoff_date: date | None,
    artifact_path_pt: str | None,
    work_dir: str,
    model_name: str,
) -> ForecastModelRun:
    run = ForecastModelRun(
        scope=scope,
        model_family=model_family,
        cell_type=cell_type,
        horizon_days=horizon_days,
        transform=transform,
        hyperparams_json=hyperparams_json,
        training_crypto_ids=training_crypto_ids,
        train_start_date=train_start_date,
        train_end_date=train_end_date,
        cutoff_date=cutoff_date,
        artifact_path_pt=artifact_path_pt,
        work_dir=work_dir,
        model_name=model_name,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def finalize_model_run(
    session,
    model_run_id: int,
    artifact_path_pt: str | None = None,
    cutoff_date: date | None = None,
) -> ForecastModelRun:
    run = session.get(ForecastModelRun, model_run_id)
    if run is None:
        raise ValueError("Model run not found")
    if artifact_path_pt is not None:
        run.artifact_path_pt = artifact_path_pt
    if cutoff_date is not None:
        run.cutoff_date = cutoff_date
    session.commit()
    session.refresh(run)
    return run


def find_latest_model_run(
    session,
    scope: str,
    model_family: str,
    cell_type: str,
    horizon_days: int,
    transform: str,
    hyperparams_json: dict[str, Any],
) -> ForecastModelRun | None:
    if hyperparams_json is None:
        hyperparams_filter = ForecastModelRun.hyperparams_json.is_(None)
    else:
        bind = getattr(session, "bind", None)
        dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
        if dialect_name == "postgresql":
            hyperparams_filter = cast(
                ForecastModelRun.hyperparams_json, JSONB
            ) == bindparam(
                "hyperparams_json",
                hyperparams_json,
                type_=JSONB,
            )
        else:
            hyperparams_filter = (
                ForecastModelRun.hyperparams_json == hyperparams_json
            )
    stmt = (
        select(ForecastModelRun)
        .where(ForecastModelRun.scope == scope)
        .where(ForecastModelRun.model_family == model_family)
        .where(ForecastModelRun.cell_type == cell_type)
        .where(ForecastModelRun.horizon_days == horizon_days)
        .where(ForecastModelRun.transform == transform)
        .where(hyperparams_filter)
        .order_by(ForecastModelRun.created_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def find_latest_model_run_any(
    session,
    scope: str,
    model_family: str,
    cell_type: str,
    horizon_days: int,
    transform: str,
) -> ForecastModelRun | None:
    stmt = (
        select(ForecastModelRun)
        .where(ForecastModelRun.scope == scope)
        .where(ForecastModelRun.model_family == model_family)
        .where(ForecastModelRun.cell_type == cell_type)
        .where(ForecastModelRun.horizon_days == horizon_days)
        .where(ForecastModelRun.transform == transform)
        .order_by(ForecastModelRun.created_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def _resolve_model_class(model_family: str):
    if model_family == "BlockRNNModel":
        return BlockRNNModel
    return RNNModel


def load_weights_from_checkpoint(
    model,
    model_name: str,
    work_dir: str,
    best: bool = True,
    map_location: str | None = "cpu",
) -> None:
    loader = getattr(model, "load_weights_from_checkpoint", None)
    if loader is None:
        raise RuntimeError("Model does not support loading weights.")
    kwargs: dict[str, Any] = {
        "model_name": model_name,
        "work_dir": work_dir,
        "best": best,
    }
    if map_location:
        kwargs["map_location"] = map_location
    try:
        loader(**kwargs)
        return
    except TypeError:
        loader(model_name, work_dir=work_dir, best=best, map_location=map_location)


def load_global_model(
    run: ForecastModelRun,
    prefer: str = "best_checkpoint",
    map_location: str | None = "cpu",
):
    model_cls = _resolve_model_class(run.model_family)
    if model_cls is None:
        raise RuntimeError("Darts model classes not available.")
    artifact_path = run.artifact_path_pt or ""
    has_artifact = bool(
        artifact_path
        and os.path.isfile(artifact_path)
        and os.path.isfile(f"{artifact_path}.ckpt")
    )
    if prefer == "best_checkpoint" and run.work_dir and run.model_name:
        base_path = os.path.join(run.work_dir, run.model_name, "_model.pth.tar")
        checkpoints_dirs = [
            os.path.join(run.work_dir, run.model_name, "checkpoints"),
            os.path.join(
                run.work_dir, "darts_logs", run.model_name, "checkpoints"
            ),
        ]
        has_best_checkpoint = False
        if os.path.isfile(base_path):
            for checkpoints_dir in checkpoints_dirs:
                try:
                    if any(
                        name.startswith("best-")
                        for name in os.listdir(checkpoints_dir)
                    ):
                        has_best_checkpoint = True
                        break
                except FileNotFoundError:
                    continue
        if not has_best_checkpoint:
            prefer = "artifact"
    if prefer == "best_checkpoint":
        try:
            kwargs: dict[str, Any] = {
                "work_dir": run.work_dir,
                "best": True,
            }
            if map_location:
                kwargs["map_location"] = map_location
            return model_cls.load_from_checkpoint(run.model_name, **kwargs)
        except Exception as exc:  # pragma: no cover - fallback path
            logger.warning("Checkpoint load failed (%s). Trying .pt.", exc)
    if not has_artifact:
        raise RuntimeError("Model artifact path missing.")
    return model_cls.load(artifact_path)
