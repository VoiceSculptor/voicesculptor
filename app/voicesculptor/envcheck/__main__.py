"""命令行入口：python -m voicesculptor.envcheck [--json] [--fix]。

只用标准库和 config 构造精简上下文，纯净环境（依赖没装齐）也能跑出报告。
"""

import argparse
import json
import sys

from voicesculptor.config import Settings
from voicesculptor.envcheck import checks
from voicesculptor.envcheck import fixes
from voicesculptor.envcheck import runner


def _build_light_context() -> checks.CheckContext:
    """不加载 API 客户端与音色库，检测走标准库探针。"""
    return checks.CheckContext(Settings.from_env())


def _print_report(report: runner.EnvReport) -> None:
    """逐行打印检测结果。"""
    for item in report.checks:
        print(f'[{item.level.value:<4}] {item.id}  {item.message}')


def _print_fixes(outcomes: list[fixes.FixOutcome]) -> None:
    """逐行打印修复结果。"""
    for item in outcomes:
        mark = 'OK  ' if item.ok else 'SKIP'
        print(f'[{mark}] {item.id}  {item.message}')


def main(argv: list[str] | None = None) -> int:
    """执行检测；--fix 修补后复检；最终存在 FAIL 时返回退出码 1。"""
    parser = argparse.ArgumentParser(prog='python -m voicesculptor.envcheck')
    parser.add_argument('--json', action='store_true', help='输出 JSON')
    parser.add_argument('--fix', action='store_true', help='检测后尝试修复')
    parser.add_argument('--download-models',
                        action='store_true',
                        help='配合 --fix 下载缺失的模型权重（约 5.1 GB）')
    args = parser.parse_args(argv)

    ctx = _build_light_context()
    report = runner.run_all(ctx)
    outcomes = []
    before = None
    if args.fix:
        before = report
        outcomes = fixes.apply(report, ctx, download=args.download_models)
        report = runner.run_all(ctx)

    if args.json:
        payload = report.to_dict()
        if args.fix:
            payload['fixes'] = [item.to_dict() for item in outcomes]
            if before is not None:
                payload['before'] = [item.to_dict() for item in before.checks]
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if args.fix:
            print('修复前：')
            _print_report(before)
            print()
            print('修复动作：')
            _print_fixes(outcomes)
            print()
            print('修复后：')
        _print_report(report)
    return 1 if report.has_failure() else 0


if __name__ == '__main__':
    sys.exit(main())
