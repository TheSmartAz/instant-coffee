from __future__ import annotations

import argparse
from pathlib import Path

from ..services.mobile_shell import ensure_mobile_shell, validate_mobile_shell


def _render_report(report: dict) -> str:
    overall = "PASS" if report.get("passed") else "FAIL"
    lines = [f"Overall: {overall}"]
    for rule in report.get("rules", []):
        status = "PASS" if rule.get("passed") else "FAIL"
        autofix = "auto-fix" if rule.get("auto_fix") else "manual"
        line = f"- {rule.get('id')}: {status} ({autofix}) - {rule.get('description')}"
        lines.append(line)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or fix mobile shell in HTML files.")
    parser.add_argument("path", help="Path to the HTML file to validate")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply mobile shell fixes in-place before validating",
    )
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists() or not target.is_file():
        raise SystemExit(f"File not found: {target}")

    html = target.read_text(encoding="utf-8")
    if args.fix:
        fixed = ensure_mobile_shell(html)
        if fixed != html:
            target.write_text(fixed, encoding="utf-8")
        html = fixed

    report = validate_mobile_shell(html)
    print(_render_report(report))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
