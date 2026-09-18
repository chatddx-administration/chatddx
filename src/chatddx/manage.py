import asyncio

import typer

from chatddx.core import provisioning, worker

app = typer.Typer()

_ = app.command("init-data")(provisioning.init_data)
_ = app.command("wipe-data")(provisioning.wipe_data)


@app.command("run")
def worker_run():
    asyncio.run(worker.trigger())


@app.callback()
def main():
    pass
