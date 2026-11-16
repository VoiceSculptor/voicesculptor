"""命令行入口：python -m voicesculptor.envcheck [--json]。"""

import argparse
import json
import sys

from voicesculptor.api.context import build_context
from voicesculptor.config import Settings
from voicesculptor.envcheck import runner


def main(argv: list[str] | None = None) -> int:
    """执行检测并打印；存在 FAIL 时返回退出码 1。"""
    parser = argparse.ArgumentParser(prog='python -m voicesculptor.envcheck')
    parser.add_argument('--json', action='store_true', help='输出 JSON')
    args = parser.parse_args(argv)
    ctx = build_context(Settings.from_env())
    report = runner.run_all(ctx)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False))
    else:
        for item in report.checks:
            print(f'[{item.level.value:<4}] {item.id}  {item.message}')
    return 1 if report.has_failure() else 0


if __name__ == '__main__':
    sys.exit(main())
