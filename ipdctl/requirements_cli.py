"""CLI adapters keep machine contracts identical in both presentation locales."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .documents import load_pack, template
from .requirements import apply_plan, preview, projection, read_registry
from .state import load_state


def register_commands(commands, translator) -> None:
    zh = translator.locale == "zh-CN"
    parser = commands.add_parser('work-plan', help='支撑成果交付规划（只读）' if zh else 'Plan supporting deliverables (read-only)', translator=translator)
    parser.add_argument('target', nargs='?', default='.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--request', help='交付规划请求' if zh else 'Work planning request')
    group.add_argument('--check-plan', help='核对已保存计划是否仍适用' if zh else 'Check saved plan freshness')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(handler=run_work_plan)
    description = "需求、增量及交付件计划" if zh else "Requirement, increment and document plans"
    parser = commands.add_parser("requirements", help=description, description=description, translator=translator)
    parser.add_argument("target", nargs="?", default=".")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--request", help="零写入预览请求 YAML/JSON" if zh else "Request YAML/JSON for a zero-write preview")
    group.add_argument("--apply", help="应用已保存的预览 JSON" if zh else "Apply saved preview JSON")
    parser.add_argument("--actor", default="")
    parser.add_argument("--authorized", action="store_true", help="声明已有明确人类授权" if zh else "Assert explicit human authorization")
    parser.add_argument("--locale", choices=("en", "zh-CN"))
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(handler=run_requirements)
    description = "中英文 Markdown 模板目录和预览" if zh else "Bilingual Markdown template catalog and preview"
    parser = commands.add_parser("templates", help=description, description=description, translator=translator)
    parser.add_argument("target", nargs="?", default=".")
    parser.add_argument("--type", dest="document_type")
    parser.add_argument("--locale", choices=("en", "zh-CN"))
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(handler=run_templates)


def run_requirements(args: argparse.Namespace) -> int:
    root = Path(args.target).resolve()
    if args.request:
        result = preview(root, load_state(args.request))
    elif args.apply:
        result = apply_plan(root, load_state(args.apply), actor=args.actor, authorized=args.authorized)
    else:
        result = projection(root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_work_plan(args):
    from .work_planning import preview as work_preview, check
    root = Path(args.target).resolve()
    result = work_preview(root, load_state(args.request)) if args.request else check(root, load_state(args.check_plan))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


def run_templates(args: argparse.Namespace) -> int:
    root = Path(args.target).resolve()
    registry = read_registry(root)
    pin = registry["template_pack"] if registry else None
    manifest, _ = load_pack(root, pin)
    if args.document_type:
        locale = args.locale or args._translator.locale
        if pin is None:
            from .documents import digest
            pin = {"id": manifest["id"], "version": manifest["version"], "sha256": digest(manifest), "path": ""}
        _, text = template(root, pin, args.document_type, locale)
        print(text, end="")
    else:
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
