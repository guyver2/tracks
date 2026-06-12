from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session

from app.db.models import (
    Objective,
    ObjectiveActivityType,
    ObjectiveMetric,
    ObjectivePeriod,
)
from app.db.session import get_db
from app.services.objectives import all_objectives_with_progress, period_dates

router = APIRouter(prefix="/objectives", tags=["objectives"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _get_objective_or_404(db: Session, objective_id: int) -> Objective:
    obj = db.get(Objective, objective_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")
    return obj


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _validate_objective(activity_type: ObjectiveActivityType, metric: ObjectiveMetric) -> None:
    if activity_type == ObjectiveActivityType.climbing and metric != ObjectiveMetric.activity_count:
        raise HTTPException(
            status_code=400,
            detail="Climbing objectives only support activity count",
        )
    if activity_type == ObjectiveActivityType.swimming and metric == ObjectiveMetric.elevation_gain_m:
        raise HTTPException(
            status_code=400,
            detail="Swimming objectives do not support elevation",
        )


@router.get("", response_class=HTMLResponse)
def list_objectives(request: Request, db: Annotated[Session, Depends(get_db)]):
    items = all_objectives_with_progress(db)
    return templates.TemplateResponse(
        request,
        "objectives/list.html",
        {"request": request, "active_nav": "objectives", "items": items},
    )


@router.get("/new", response_class=HTMLResponse)
def new_objective_form(request: Request):
    return templates.TemplateResponse(
        request,
        "objectives/form.html",
        {
            "request": request,
            "active_nav": "objectives",
            "objective": None,
            "form_action": "/objectives",
        },
    )


@router.post("")
def create_objective(
    db: Annotated[Session, Depends(get_db)],
    metric: Annotated[str, Form()],
    activity_type: Annotated[str, Form()],
    target_value: Annotated[float, Form()],
    period: Annotated[str, Form()],
    label: Annotated[str, Form()] = "",
    start_date: Annotated[str, Form()] = "",
    end_date: Annotated[str, Form()] = "",
):
    if period == "custom":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Custom period requires dates")
        start, end = _parse_date(start_date), _parse_date(end_date)
    else:
        start, end = period_dates(ObjectivePeriod(period))

    parsed_type = ObjectiveActivityType(activity_type)
    parsed_metric = ObjectiveMetric(metric)
    _validate_objective(parsed_type, parsed_metric)

    obj = Objective(
        metric=parsed_metric,
        activity_type=parsed_type,
        target_value=target_value,
        period=ObjectivePeriod(period),
        start_date=start,
        end_date=end,
        label=label.strip() or None,
    )
    db.add(obj)
    db.commit()
    return RedirectResponse(url="/objectives", status_code=303)


@router.get("/{objective_id}/edit", response_class=HTMLResponse)
def edit_objective_form(
    request: Request,
    objective_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    objective = _get_objective_or_404(db, objective_id)
    return templates.TemplateResponse(
        request,
        "objectives/form.html",
        {
            "request": request,
            "active_nav": "objectives",
            "objective": objective,
            "form_action": f"/objectives/{objective_id}",
        },
    )


@router.post("/{objective_id}")
def update_objective(
    objective_id: int,
    db: Annotated[Session, Depends(get_db)],
    metric: Annotated[str, Form()],
    activity_type: Annotated[str, Form()],
    target_value: Annotated[float, Form()],
    period: Annotated[str, Form()],
    label: Annotated[str, Form()] = "",
    start_date: Annotated[str, Form()] = "",
    end_date: Annotated[str, Form()] = "",
):
    obj = _get_objective_or_404(db, objective_id)

    if period == "custom":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Custom period requires dates")
        start, end = _parse_date(start_date), _parse_date(end_date)
    else:
        start, end = period_dates(ObjectivePeriod(period))

    parsed_type = ObjectiveActivityType(activity_type)
    parsed_metric = ObjectiveMetric(metric)
    _validate_objective(parsed_type, parsed_metric)

    obj.metric = parsed_metric
    obj.activity_type = parsed_type
    obj.target_value = target_value
    obj.period = ObjectivePeriod(period)
    obj.start_date = start
    obj.end_date = end
    obj.label = label.strip() or None
    db.commit()
    return RedirectResponse(url="/objectives", status_code=303)


@router.post("/{objective_id}/delete")
def delete_objective(objective_id: int, db: Annotated[Session, Depends(get_db)]):
    obj = _get_objective_or_404(db, objective_id)
    db.delete(obj)
    db.commit()
    return RedirectResponse(url="/objectives", status_code=303)
