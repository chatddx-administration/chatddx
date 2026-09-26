import django
import typer

django.setup()

from chatddx.core import provisioning
from chatddx.dev import fake_vllm
from chatddx.logs import cli as logs
from chatddx.repl import cli
from chatddx.worker import cli as worker

app = typer.Typer()

_ = app.command("init-data")(provisioning.init_data)
_ = app.command("wipe-data")(provisioning.wipe_data)
_ = app.command("repl")(cli.repl)
_ = app.command("fake-vllm")(fake_vllm.fake_vllm)
_ = app.command("agreement")(logs.agreement)
app.add_typer(worker.app, name="worker")


@app.callback()
def main():
    pass
