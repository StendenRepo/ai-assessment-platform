"""Module API routes — overlap."""
from .router import router
from .shared import *  # noqa: F403

@router.get("/{module_id}/overlap/signals", response_model=List[OverlapSignalOut])
def list_module_overlap_signals(
    module_id: str,
    status: Optional[str] = Query(None, description="confirmed or possible"),
    scope: Optional[str] = Query(None, description="within_group or cross_group"),
    group_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    signals = OverlapService.get_module_signals(
        db,
        str(module.id),
        status=status,
        scope=scope,
        group_id=group_id,
    )
    student_names, evidence_names = _module_signal_context(db, module)
    return [_signal_to_out(signal, student_names, evidence_names) for signal in signals]


@router.get("/{module_id}/overlap/signals/{signal_id}", response_model=OverlapSignalOut)
def get_module_overlap_signal(
    module_id: str,
    signal_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    signal = OverlapService.get_signal(db, str(module.id), signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Overlap signal not found")
    student_names, evidence_names = _module_signal_context(db, module)
    return _signal_to_out(
        signal,
        student_names,
        evidence_names,
        db=db,
        include_documents=True,
    )


@router.post("/{module_id}/overlap/analyze", response_model=OverlapAnalysisOut)
def analyze_module_overlap(
    module_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    generated = OverlapService.analyze_module_overlap(db, str(module.id))
    warning_data = OverlapService.build_warning(generated)
    student_names, evidence_names = _module_signal_context(db, module)

    audit_service.log_action(
        db,
        action="overlap.analyzed",
        source=AuditSource.ai,
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "signal_count": len(generated),
            "high_risk_count": warning_data.get("high_risk_count", 0),
            "has_overlap": warning_data.get("has_overlap", False),
        },
        ip_address=request.client.host if request.client else None,
    )

    return OverlapAnalysisOut(
        module_id=str(module.id),
        generated_count=len(generated),
        warning=OverlapWarningOut(**warning_data),
        signals=[_signal_to_out(signal, student_names, evidence_names) for signal in generated],
    )


@router.get("/{module_id}/overlap/warning", response_model=OverlapWarningOut)
def get_module_overlap_warning(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    signals = OverlapService.get_module_signals(db, str(module.id))
    warning_data = OverlapService.build_warning(signals)
    return OverlapWarningOut(**warning_data)

