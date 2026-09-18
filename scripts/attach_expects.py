import tomllib
from pathlib import Path

import tomli_w


def read_path(directory):
    return {
        path.name: path.read_text()
        for path in Path(directory).iterdir()
        if path.is_file()
    }


expects = read_path("../src/chatddx/data/expects")

path = Path("../src/chatddx/data/tags.toml")

data = tomllib.loads(path.read_text())

for case, expect in list(expects.items()):
    expects.pop(case)
    data["case"][case]["expects"] = {"regex_match": expect}
print(expect)
path.write_text(tomli_w.dumps(data))
