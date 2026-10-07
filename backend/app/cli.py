from __future__ import annotations

import argparse
import json

from app.services.catalog_sync import run_sync


def main() -> None:
    parser = argparse.ArgumentParser(prog='anivideos')
    subparsers = parser.add_subparsers(dest='command', required=True)
    sync = subparsers.add_parser('sync-content', help='Import and cache legal catalog metadata in PostgreSQL.')
    sync.add_argument('--source', choices=('all', 'anilist', 'tmdb'), default='all')
    sync.add_argument('--pages', type=int, default=1)
    args = parser.parse_args()
    if args.command == 'sync-content':
        result = run_sync(source=args.source, pages=max(1, min(args.pages, 5)))
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
