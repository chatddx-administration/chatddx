import subprocess
from importlib.metadata import version
from pathlib import Path

from chatddx.runtime.client import PACKAGES, build_of, running


def test_a_build_is_the_store_path_chatddx_runs_from():
    store = "/nix/store/2ggzfi36z2c9gckn3fp4mgij41wyf7la-chatddx-django-b585cec"
    installed = Path(f"{store}/lib/python3.13/site-packages/chatddx/__init__.py")

    assert build_of(installed) == store
    assert build_of(Path("/home/user/chatddx/src/chatddx/__init__.py")) is None


def test_a_dev_shell_runs_at_the_checkout_s_revision():
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    client = running()

    assert client.build is None
    assert client.rev is not None
    assert client.rev.removesuffix("-dirty") == head
    assert client.trail.build is None
    assert client.packages == {package: version(package) for package in PACKAGES}
