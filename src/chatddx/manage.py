import django
import typer

django.setup()

from chatddx.core import provisioning
from chatddx.repl import cli
from chatddx.dev import fake_vllm

app = typer.Typer()

_ = app.command("init-data")(provisioning.init_data)
_ = app.command("wipe-data")(provisioning.wipe_data)
_ = app.command("repl")(cli.repl)
_ = app.command("fake-vllm")(fake_vllm.fake_vllm)


@app.callback()
def main():
    pass
