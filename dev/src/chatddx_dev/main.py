import argparse
from collections.abc import Sequence
from pathlib import Path

from chatddx_dev import costs, index, project, refcheck, stamp


def _stamp(args: argparse.Namespace) -> None:
    if args.stamping == "check":
        stamp.check()
    elif args.stamping == "pending":
        stamp.pending()
    elif args.stamping == "docs":
        stamp.docs(args.base, args.check)
    else:
        stamp.reflow(args.check)


def _index(args: argparse.Namespace) -> None:
    if args.check:
        index.check(args.part, args.kind)
    else:
        index.write(args.part, args.kind)


def _facts(args: argparse.Namespace) -> None:
    print(index.facts(args.path))


def _refcheck(_: argparse.Namespace) -> None:
    try:
        found = refcheck.check()
    except ValueError as e:
        raise SystemExit(f"refcheck: {e}") from None
    if found:
        print("\n".join(found))
        raise SystemExit(1)


def _costs(args: argparse.Namespace) -> None:
    if args.costing == "write":
        costs.write()
    else:
        costs.show()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="chatddx-dev")
    commands = parser.add_subparsers(required=True)

    indexing = commands.add_parser(
        "index",
        help="write, from each part's code, whatever its language, the indexes behind "
        + "it: its surface in docs/surfaces/, its comments in docs/comments/, its "
        + "whoopses and asserts in docs/whoopses/ and the messages it says in "
        + "docs/catalog/, with what changed as stamps pending, and say how many",
    )
    _ = indexing.add_argument(
        "kind",
        nargs="*",
        choices=index.KINDS,
        help="the kinds of index to write, or all of them",
    )
    _ = indexing.add_argument(
        "--part",
        action="append",
        default=[],
        choices=project.PARTS,
        help="a part to write the indexes of, again for another, or all of them",
    )
    _ = indexing.add_argument(
        "--check",
        action="store_true",
        help="write nothing; fail while an index is behind the code, and, of all of "
        + "them, flag what parts hold amiss",
    )
    indexing.set_defaults(run=_index)

    facting = commands.add_parser(
        "facts",
        help="write nothing; print, as JSON, the facts the indexes are written from: "
        + "each file's names, comments, claims and surface's entries, as an extractor "
        + "in any language gives them",
    )
    _ = facting.add_argument("path", nargs="+", type=Path, help="the files to read")
    facting.set_defaults(run=_facts)

    stamping = commands.add_parser(
        "stamp",
        help="the docs as an agent wrote them and the catalogs, with what changed as a "
        + "git conflict to stamp",
    )
    stamp_commands = stamping.add_subparsers(required=True)
    stamp_check = stamp_commands.add_parser(
        "check",
        help="write nothing; fail while a doc, an index or a catalog holds a conflict "
        + "that isn't a stamp",
    )
    stamp_check.set_defaults(run=_stamp, stamping="check")
    stamp_pending = stamp_commands.add_parser(
        "pending",
        help="write nothing; flag each doc's stamps pending, and fail while one is",
    )
    stamp_pending.set_defaults(run=_stamp, stamping="pending")
    stamp_docs = stamp_commands.add_parser(
        "docs",
        help="keep each change to a doc since a commit as stamps pending, and say "
        + "against what and how many",
    )
    _ = stamp_docs.add_argument(
        "base",
        help="the commit whose docs are as signed, such as dev/stamped.sh tells",
    )
    _ = stamp_docs.add_argument(
        "--check",
        action="store_true",
        help="write nothing; fail, saying which, while a doc is behind",
    )
    stamp_docs.set_defaults(run=_stamp, stamping="docs")
    stamp_reflow = stamp_commands.add_parser(
        "reflow",
        help="format the frontend and the docs with prettier, a doc holding stamps "
        + "pending a side of its stamps at a time",
    )
    _ = stamp_reflow.add_argument(
        "--check",
        action="store_true",
        help="write nothing; fail, saying which, while one is unformatted",
    )
    stamp_reflow.set_defaults(run=_stamp, stamping="reflow")

    refchecking = commands.add_parser(
        "refcheck",
        help="check what the docs refer to: files, their sections, code, the "
        + "glossary's terms and commits on main",
    )
    refchecking.set_defaults(run=_refcheck)

    costing = commands.add_parser(
        "costs",
        help="what dev/check.sh's checks, its frontend tests and pytest's runs took, as "
        + "dev/costs.tsv logs it, and the figures the docs quote off it",
    )
    cost_commands = costing.add_subparsers(required=True)
    cost_show = cost_commands.add_parser(
        "show",
        help="write nothing; print each command's median per machine class",
    )
    cost_show.set_defaults(run=_costs, costing="show")
    cost_write = cost_commands.add_parser(
        "write",
        help="fold what was timed since into dev/costs.tsv, and rewrite the figures "
        + f"the docs quote for the {project.COSTS_QUOTED} machine class that are off",
    )
    cost_write.set_defaults(run=_costs, costing="write")

    args = parser.parse_args(argv)
    args.run(args)
