# pyright: basic
from django.contrib import admin
from django.db.models import Manager

from chatddx.core.models import IdentityModel


class Sharable:
    collaborators: Manager[IdentityModel]

    @admin.display(description="Collaborators")
    def collaborators_csv(self):
        return ", ".join([str(c) for c in self.collaborators.all()]) or None
