from __future__ import annotations

from datetime import datetime
from typing import Any, override

from django.db.models import (
    PROTECT,
    CharField,
    DateTimeField,
    ForeignKey,
    Index,
    Manager,
    ManyToManyField,
)
from django.db.models import Field as DjangoField
from django.db.models import Model as DjangoModel
from ninja import Schema as NinjaSchema
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    computed_field,
)

from chatddx.core.fields import CoercedStr, NullableStr
from chatddx.core.models import IdentityModel
from chatddx.core.schemas import IdentitySpec
from chatddx.registry.schemas import RegistryInstance
from chatddx.utils import generate_fingerprint


class BranchProxy:
    pk: int
    name: str
    objects: Manager[BranchModel]
    target: TrailModel

    @override
    def __str__(self) -> str:
        return self.name


class BranchBase(BaseModel):
    owner_id: int
    collaborators: list[Any]
    name: str
    timestamp: datetime | None = None


class TrailSchema(RegistryInstance):
    model_config = ConfigDict(from_attributes=True)
    _name: str | None = PrivateAttr()

    @computed_field
    def fingerprint(self) -> str:
        return self.as_fingerprint()

    def as_fingerprint(self):
        serialized = self.model_dump(exclude={"fingerprint"})
        return generate_fingerprint(serialized)


class TrailSchemaRef(BaseModel):
    fingerprint: str


class BranchSchema[T: TrailSchema](BranchBase):
    target_type: type[T]
    target_id: int


class BranchModel(DjangoModel):
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
    )
    name = CharField(max_length=255)
    timestamp = DateTimeField(
        auto_now_add=True,
    )
    target: DjangoField[Any, Any]

    collaborators = ManyToManyField(
        IdentityModel,
        blank=True,
        related_name="shared_%(class)s",
    )

    class Meta:
        abstract = True
        indexes = [
            Index(fields=["owner", "name", "-timestamp"]),
        ]

    def as_proxy(self, proxy_model: type[BranchProxy]):
        return proxy_model.from_db(
            db=self._state.db,
            field_names=[f.name for f in self._meta.fields],
            values=[getattr(self, f.name) for f in self._meta.fields],
        )


class TrailSpec(NinjaSchema):
    id: int
    fingerprint: str
    timestamp: datetime


class BranchSpec[T: TrailSpec](BranchBase, NinjaSchema):
    id: int
    target: T


class BaseFormDataIn(NinjaSchema):
    name: NullableStr = None
    owner: IdentitySpec | None = None
    collaborators: list[IdentitySpec] = Field(default_factory=list)


class BaseFormDataOut(BaseModel):
    id: CoercedStr
    name: str = ""


class TrailModel(DjangoModel):
    fingerprint = CharField(
        max_length=64,
        db_index=True,
        editable=False,
        unique=True,
    )
    timestamp = DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        abstract = True

    @override
    def __str__(self):
        name = getattr(self, "branch_name", None)
        short_hash = self.fingerprint[:6]
        return f"{name} ({short_hash})" if name else short_hash
