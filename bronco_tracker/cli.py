"""Command-line entry points for the Bronco tracker.

    python -m bronco_tracker.cli add --id ... --dealer ... --trim ... \\
        --color ... --price 44169 --url ... [--location ...] [--stock ...] \\
        [--fog-lights] [--camera-360]
    python -m bronco_tracker.cli remove --id ...
    python -m bronco_tracker.cli report

A listing with BOTH --fog-lights and --camera-360 lands in the "upgraded"
category (see bronco_tracker/budget.py) with a bit more budget headroom.
"""
from __future__ import annotations

import argparse

from . import report, storage


def cmd_add(args: argparse.Namespace) -> None:
    fields = {
        "dealer": args.dealer,
        "location": args.location,
        "trim": args.trim,
        "doors": args.doors,
        "color_exterior": args.color,
        "price": args.price,
        "msrp": args.msrp,
        "stock_number": args.stock,
        "url": args.url,
        "has_fog_lights": args.fog_lights,
        "has_360_camera": args.camera_360,
    }
    fields = {k: v for k, v in fields.items() if v is not None}
    record = storage.upsert_listing(args.id, fields)
    print(f"Saved {record['id']}: {record.get('trim')} {record.get('color_exterior')} "
          f"${record.get('price')} @ {record.get('dealer')}")


def cmd_remove(args: argparse.Namespace) -> None:
    storage.mark_removed(args.id, status=args.status)
    print(f"Marked {args.id} as {args.status}")


def cmd_report(args: argparse.Namespace) -> None:
    text = report.write_report()
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bronco deal tracker")
    sub = parser.add_subparsers(required=True)

    p_add = sub.add_parser("add", help="Add or update a tracked listing")
    p_add.add_argument("--id", required=True, help="Stable id, e.g. dealer-slug-stocknumber")
    p_add.add_argument("--dealer")
    p_add.add_argument("--location")
    p_add.add_argument("--trim")
    p_add.add_argument("--doors", type=int)
    p_add.add_argument("--color")
    p_add.add_argument("--price", type=int)
    p_add.add_argument("--msrp", type=int, help="Sticker/MSRP, if different from --price (shows as savings)")
    p_add.add_argument("--stock")
    p_add.add_argument("--url")
    p_add.add_argument("--fog-lights", dest="fog_lights", action=argparse.BooleanOptionalAction, default=None)
    p_add.add_argument("--camera-360", dest="camera_360", action=argparse.BooleanOptionalAction, default=None)
    p_add.set_defaults(func=cmd_add)

    p_rm = sub.add_parser("remove", help="Mark a listing sold/removed")
    p_rm.add_argument("--id", required=True)
    p_rm.add_argument("--status", default="removed", choices=["removed", "sold"])
    p_rm.set_defaults(func=cmd_remove)

    p_report = sub.add_parser("report", help="Regenerate data/report.md")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
