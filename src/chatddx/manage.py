import django
import typer

django.setup()

from chatddx.core import provisioning

app = typer.Typer()

_ = app.command("init-data")(provisioning.init_data)
_ = app.command("wipe-data")(provisioning.wipe_data)


@app.callback()
def main():
    pass
