# pyright: basic
"""The cell a client names in each request: show, reasoning, scorers and save."""

from typing import Any, get_args

from django.http import HttpRequest
from ninja import Query, Router
from ninja.errors import HttpError

from chatddx.django.api.identity import identity_of
from chatddx.django.api.schemas import (
    CASE,
    CellIn,
    CellOut,
    Detail,
    HeldTo,
    Realization,
    ReasoningTable,
    Resolved,
    Saved,
    SaveIn,
    ScorerOut,
    ShowIn,
    StackRealizations,
)
from chatddx.django.api.showing import detail_of
from chatddx.repl.bench import Bench, greedy
from chatddx.repl.cell import NONE, SLICES
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.reasoning.pydantic import Effort, ReasoningBranchOut
from chatddx.repo.entities.scorer.pydantic import ScorerTrailOut
from chatddx.repo.entities.stack.pydantic import StackBranchOut
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.store.branch import (
    get_visible_branch_model,
    select_visible_branch_models,
)
from chatddx.runtime.resolution import (
    CellRefused,
    Resolution,
    SliceRefusal,
    realize,
)
from chatddx.scoring.score import Scoring

EFFORTS: tuple[Effort, ...] = get_args(Effort.__value__)

STACK_PARTS: tuple[EntityName, ...] = ("machine", "os", "llm", "serving")

router = Router(tags=["cell"])


def held(request: HttpRequest, cell: CellIn, transport: Any = None) -> Bench:
    """A bench holding the cell, put together as `use`, `on` and `set` would."""
    bench = Bench(identity_of(request), transport)

    if cell.configuration is not None:
        bench.cell.put(
            bench.configuration_named(cell.configuration),
            bench.called(cell.configuration),
        )

    if cell.stack is not None:
        bench.cell.stack = StackBranchOut.model_validate(
            get_visible_branch_model("stack", bench.identity, cell.stack)
        )

    for entity in SLICES:
        name = getattr(cell, entity)

        if name is None:
            continue

        if not bench.cell.configuration:
            raise HttpError(
                400, f"the cell has no configuration to set its {entity} in"
            )

        variation = None if name == NONE else bench.variation_named(entity, name)

        try:
            bench.cell.set(entity, variation)
        except ValueError as e:
            raise HttpError(400, str(e)) from None

    return bench


@router.get("/cell", response=CellOut)
def show(request: HttpRequest, cell: Query[ShowIn]):
    """
    The cell, how it resolves on its stack, and the cases each scorer can hold
    it to: those with any `tag`, or all.
    """
    bench = held(request, cell)
    held_cell = bench.cell

    if not (held_cell.configuration or held_cell.stack):
        raise HttpError(
            400, "the cell is empty: name a configuration, a stack, or both"
        )

    cases = bench.cases(cell.tag) if held_cell.configuration else None

    if cell.tag and cases == []:
        raise HttpError(
            404, f"no case tagged {' or '.join(cell.tag)} for {bench.identity}"
        )

    return CellOut(
        label=held_cell.label or None,
        configuration=held_cell.configuration,
        set=held_cell.variations,
        stack=held_cell.stack,
        resolution=(
            _resolved(bench) if held_cell.configuration and held_cell.stack else None
        ),
        cases=None if cases is None else len(cases),
        tags=cell.tag,
        scorers=(
            None
            if cases is None
            else [
                HeldTo(
                    scorer=held.scorer.name,
                    view=held.scorer.view,
                    target_kind=held.scorer.target_kind,
                    offered=held.offered,
                    have=held.have if held.offered else 0,
                    missing=held.missing,
                    unread=held.unread,
                )
                for held in bench.held_to(cases)
            ]
        ),
    )


def _resolved(bench: Bench) -> Resolved:
    resolution: Resolution | None = None

    try:
        resolution = bench.resolve()
        parts: Any = resolution
        refusals: list[SliceRefusal] = []
    except CellRefused as e:
        parts, refusals = e, e.refusals

    system, user = resolution.render(CASE) if resolution else (None, None)

    return Resolved(
        refusals=refusals,
        reasoning=parts.reasoning,
        sampling=parts.sampling,
        greedy=parts.sampling is not None and greedy(parts.sampling),
        coercion=parts.coercion,
        tools=parts.tools,
        slots=parts.slots,
        fields=resolution.fields if resolution else None,
        system=system,
        user=user,
    )


@router.get("/reasoning", response=ReasoningTable)
def reasoning(request: HttpRequest, cell: Query[CellIn]):
    """What each reasoning variation does on each stack, with the cell's sampling."""
    bench = held(request, cell)
    # the cell's trails, as the repo's schemas have them
    slices: Any = bench.cell.slices if bench.cell.configuration else None
    variations = sorted(
        (
            ReasoningBranchOut.model_validate(model)
            for model in select_visible_branch_models("reasoning", bench.identity)
        ),
        key=lambda v: (EFFORTS.index(v.trail.effort), v.trail.budget or 0, v.name),
    )

    return ReasoningTable(
        sampling=slices.sampling if slices else None,
        current=slices.reasoning.fingerprint if slices else None,
        variations=variations,
        stacks=[
            StackRealizations(
                stack=stack.name,
                current=bench.cell.stack is not None
                and bench.cell.stack.name == stack.name,
                realizations=[
                    _realization(
                        realize(
                            variation.trail,
                            slices.sampling if slices else None,
                            bench.facts_of(stack),
                            stack.trail.serving,
                        )
                    )
                    for variation in variations
                ],
            )
            for stack in bench.stacks()
        ],
    )


def _realization(realized: Any) -> Realization:
    reasoning, sampling, refusals = realized
    return Realization(reasoning=reasoning, sampling=sampling, refusals=refusals)


@router.get("/scorers", response=list[ScorerOut])
def scorers(request: HttpRequest, cell: Query[CellIn]):
    """The scorers, what each reads, and whether the cell's output offers it."""
    bench = held(request, cell)
    offered = bench.cell.slices.output.views if bench.cell.configuration else None

    return [
        ScorerOut(
            name=scorer.name,
            owner=scorer.owner,
            trail=ScorerTrailOut.model_validate(scorer.trail),
            metrics=list(scorer.metrics),
            offered=None if offered is None else scorer.view in offered,
        )
        for scorer in Scoring(bench.identity).scorers
    ]


@router.post("/cell/save", response=Saved)
def save(request: HttpRequest, cell: SaveIn):
    """Save the cell's configuration as the identity's own; what it reaches too."""
    bench = held(request, cell)

    if not bench.cell.configuration:
        raise HttpError(400, "the cell has no configuration to save")

    try:
        saved = bench.save(cell.name)
    except ValueError as e:
        raise HttpError(400, str(e)) from None

    return Saved(
        what=saved.what, copied=saved.copied, configuration=bench.cell.configuration
    )


def _part(entity: EntityName):
    def part(request: HttpRequest, cell: Query[CellIn]):
        bench = held(request, cell)
        return detail_of(bench, entity, _in_cell(bench, cell, entity))

    return part


# the cell's own of each entity it has, as show ENTITY shows it
for _entity in ("configuration", "stack", *SLICES, *STACK_PARTS):
    router.add_api_operation(
        f"/cell/{_entity}",
        ["GET"],
        _part(_entity),
        response=Detail[entity_of(_entity).branch_out],
        operation_id=f"cell_{_entity}",
        summary=f"The cell's {_entity}, and the identity's runs with it",
    )


def _in_cell(bench: Bench, cell: CellIn, entity: EntityName) -> BranchModel:
    trail: Any = None

    if entity == "configuration" or entity in SLICES:
        if cell.configuration is None or bench.cell.configuration is None:
            raise HttpError(400, "the cell has no configuration")

        if entity == "configuration":
            return bench.configuration_named(cell.configuration)

        name = getattr(cell, entity)

        if name is not None and name != NONE:
            return get_visible_branch_model(entity, bench.identity, name)

        trail = None if name == NONE else bench.cell.variation(entity)
    else:
        if cell.stack is None or bench.cell.stack is None:
            raise HttpError(400, "the cell has no stack")

        if entity == "stack":
            return get_visible_branch_model("stack", bench.identity, cell.stack)

        trail = getattr(bench.cell.stack.trail, entity)

    if trail is None:
        raise HttpError(404, f"the cell has no {entity}")

    return get_visible_branch_model(entity, bench.identity, trail=trail.id)
