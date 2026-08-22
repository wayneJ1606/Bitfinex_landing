"""Local entry point for the dashboard-first experimental product."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .p0_experimental_dashboard import export_experimental_dashboard
from .p0_experimental_payload import build_experimental_payload


@dataclass(frozen=True)
class ExperimentalPipelineSummary:
    status: str
    json_path: Path
    dashboard_path: Path


def run_experimental_pipeline(
    *,
    modeling_root: Path,
    market_root: Path,
    output_root: Path,
    generated_at: str,
) -> ExperimentalPipelineSummary:
    """Publish JSON and HTML from local public/model artifacts only."""
    output_root = Path(output_root)
    payload = build_experimental_payload(
        Path(modeling_root), Path(market_root), generated_at=generated_at
    )
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "dashboard_data.json"
    temporary = json_path.with_suffix(json_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    json.loads(temporary.read_text(encoding="utf-8"))
    temporary.replace(json_path)
    dashboard_path = export_experimental_dashboard(payload, output_root / "dashboard.html")
    return ExperimentalPipelineSummary(
        status=str(payload["status"]),
        json_path=json_path,
        dashboard_path=dashboard_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the local read-only experimental funding dashboard"
    )
    parser.add_argument("--modeling-root", type=Path, default=Path("data/modeling"))
    parser.add_argument("--market-root", type=Path, default=Path("data/market"))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/modeling/p0_experimental/latest"),
    )
    args = parser.parse_args()
    try:
        summary = run_experimental_pipeline(
            modeling_root=args.modeling_root,
            market_root=args.market_root,
            output_root=args.output_root,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"fatal: {error}", file=sys.stderr)
        return 1
    print(f"status={summary.status}")
    print(f"json={summary.json_path}")
    print(f"dashboard={summary.dashboard_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
