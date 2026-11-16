"""素材体检路由。"""

import os

from fastapi import APIRouter
from fastapi import Form
from fastapi import Request

from voicesculptor import audit as audit_module
from voicesculptor.api.context import get_context
from voicesculptor.errors import ValidationError

router = APIRouter()


@router.post('/api/audit')
def audit(request: Request, dir_path: str = Form(...)) -> dict:
    """对目录做体检并写 markdown 报告。"""
    if not os.path.isdir(dir_path):
        raise ValidationError('目录不存在: ' + dir_path)
    ctx = get_context(request)
    report, summary = audit_module.audit_folder(dir_path)
    report_path = audit_module.write_report(report, ctx.settings.log_dir)
    return {
        'ok': True,
        'report': report,
        'summary': summary,
        'report_path': report_path,
    }
