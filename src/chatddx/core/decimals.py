# Nothing but orm's 0001_initial reads these, and it imports them by path, so
# they stay until the migrations are squashed.
import json
from decimal import Decimal
from typing import Any, override


class DecimalEncoder(json.JSONEncoder):
    @override
    def default(self, o: Any):
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


class DecimalDecoder(json.JSONDecoder):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs, parse_float=Decimal)
