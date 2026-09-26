"""`chatddx worker`: the worker at the queue, as the host's service runs it."""

import logging
import os

import typer

from chatddx.worker import worker

app = typer.Typer(
    help="The worker, which runs the trials the portal's batches put in its queue.",
    no_args_is_help=True,
)


@app.command("serve")
def serve() -> None:
    """Run the queue as it fills, till stopped: what the host's service runs."""
    _logged()

    with worker.terminated_as_interrupted():
        try:
            worker.serve()
        except KeyboardInterrupt:
            pass


@app.command("run")
def run() -> None:
    """Run what is queued, then stop: a paused or stopped queue runs nothing."""
    _logged()

    with worker.terminated_as_interrupted():
        try:
            taken = worker.run()
        except KeyboardInterrupt:
            return

    typer.echo(f"{taken} case{'' if taken == 1 else 's'} taken from the queue")


def _logged() -> None:
    logging.basicConfig(
        level=os.environ.get("CHATDDX_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for noisy in ("httpx", "httpx2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
