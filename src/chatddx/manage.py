import asyncio

import django
import typer

django.setup()

from chatddx.core import provisioning, worker

app = typer.Typer()

worker_app = typer.Typer(help="Run queued experiments.")
_ = app.add_typer(worker_app, name="worker")

_ = app.command("init-data")(provisioning.init_data)
_ = app.command("wipe-data")(provisioning.wipe_data)


@worker_app.command("run")
def worker_run():
    """Process the queue once and exit."""
    asyncio.run(worker.drain())


@worker_app.command("serve")
def worker_serve():
    """Process the queue until killed. This is the production service."""
    asyncio.run(worker.serve())


@app.callback()
def main():
    pass
