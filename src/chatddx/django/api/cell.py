# pyright: basic
"""The cell a client names in each request: show, reasoning, scorers and save."""

from typing import Any, get_args

from django.http import HttpRequest
from ninja import Query, Router
from ninja.errors import HttpError

from chatddx.django.api.identity import identity_of
from chatddx.django.api.schemas import (
    CASE,
    BranchDetail,
    CellIn,
    CellOut,
    CoercionOut,
    HeldTo,
    OutputOut,
    Realization,
    ReasoningTable,
    ReasoningVariation,
    ResolutionOut,
    Saved,
    SaveIn,
    ScorerOut,
    ShowIn,
    SliceOut,
    StackOut,
    StackRealizations,
    ToolOut,
)
from chatddx.django.api.showing import (
    branches_of,
    detail_of,
    maybe_ref_of,
    reasoning_of,
    ref_of,
    refusals_of,
    sampling_of,
)
from chatddx.repl.bench import Bench
from chatddx.repl.cell import NONE, SLICES
from chatddx.repo.entities.coercion.pydantic import SLOT as SCHEMA_PROMPT
from chatddx.repo.entities.output.pydantic import VIEWS
from chatddx.repo.entities.reasoning.pydantic import Effort, ReasoningBranchOut
from chatddx.repo.entities.stack.pydantic import StackBranchOut
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.store.branch import (
    get_visible_branch_model,
    select_visible_branch_models,
)
from chatddx.runtime.resolution import CellRefused, Resolution, realize
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

    if not (bench.cell.configuration or bench.cell.stack):
        raise HttpError(
            400, "the cell is empty: name a configuration, a stack, or both"
        )

    return cell_of(bench, cell.tag)


def cell_of(bench: Bench, tags: list[str]) -> CellOut:
    cell = bench.cell
    configuration = cell.configuration
    cases = bench.cases(tags) if configuration else None

    if tags and cases == []:
        raise HttpError(404, f"no case tagged {' or '.join(tags)} for {bench.identity}")

    return CellOut(
        label=cell.label or None,
        configuration=(
            None
            if configuration is None
            else ref_of(bench, "configuration", configuration.trail, cell.name)
        ),
        configuration_owner=None if configuration is None else configuration.owner.name,
        slices=_slices(bench) if configuration else [],
        output=(
            None
            if configuration is None
            else OutputOut(
                free_text=cell.slices.output.json_schema is None,
                views=[view for view in VIEWS if view in cell.slices.output.views],
            )
        ),
        stack=None if cell.stack is None else _stack(bench, cell.stack),
        resolution=_resolution(bench) if configuration and cell.stack else None,
        cases=None if cases is None else len(cases),
        tags=tags,
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


def _slices(bench: Bench) -> list[SliceOut]:
    cell = bench.cell
    assert cell.configuration
    shown: list[SliceOut] = []

    for entity in SLICES:
        own = getattr(cell.configuration.trail, entity)
        variation = cell.variation(entity)
        set_ = entity in cell.variations
        name = cell.set_name(entity) if set_ else None

        shown.append(
            SliceOut(
                slice=entity,
                variation=(
                    None
                    if variation is None
                    else ref_of(bench, entity, variation, name)
                ),
                own=maybe_ref_of(bench, entity, own),
                set=set_,
            )
        )

    return shown


def _stack(bench: Bench, stack: StackBranchOut) -> StackOut:
    details = stack.details

    return StackOut(
        name=stack.name,
        owner=stack.owner.name,
        fingerprint=stack.trail.fingerprint,
        machine=ref_of(bench, "machine", stack.trail.machine),
        llm=ref_of(bench, "llm", stack.trail.llm),
        serving=maybe_ref_of(bench, "serving", stack.trail.serving),
        endpoint=None if details.endpoint is None else str(details.endpoint),
        served_name=details.served_name,
        api=details.api,
    )


def _resolution(bench: Bench) -> ResolutionOut:
    resolution: Resolution | None = None

    try:
        resolution = bench.resolve()
        refusals = []
        reasoning, sampling, coercion = (
            resolution.reasoning,
            resolution.sampling,
            resolution.coercion,
        )
        tools, slots = resolution.tools, resolution.slots
    except CellRefused as e:
        refusals = e.refusals
        reasoning, sampling, coercion = e.reasoning, e.sampling, e.coercion
        tools, slots = e.tools, e.slots

    system, user = resolution.render(CASE) if resolution else (None, None)

    return ResolutionOut(
        resolved=resolution is not None,
        refusals=refusals_of(refusals),
        reasoning=reasoning_of(reasoning),
        sampling=sampling_of(sampling),
        coercion=(
            None
            if coercion is None
            else CoercionOut(
                requested=coercion.requested,
                mode=coercion.mode,
                shown=SCHEMA_PROMPT in slots,
                tool_description=coercion.tool_description,
                note=coercion.note,
                sent=coercion.sent,
            )
        ),
        tools=[
            ToolOut(
                name=tool.name, description=tool.description, parameters=tool.parameters
            )
            for tool in tools
        ],
        slots=slots,
        fields=resolution.fields if resolution else None,
        system=system,
        user=user,
    )


@router.get("/reasoning", response=ReasoningTable)
def reasoning(request: HttpRequest, cell: Query[CellIn]):
    """What each reasoning variation does on each stack, with the cell's sampling."""
    bench = held(request, cell)
    slices = bench.cell.slices if bench.cell.configuration else None
    variations = sorted(
        (
            ReasoningBranchOut.model_validate(model)
            for model in select_visible_branch_models("reasoning", bench.identity)
        ),
        key=lambda v: (EFFORTS.index(v.trail.effort), v.trail.budget or 0, v.name),
    )
    stacks: list[StackRealizations] = []

    for stack in bench.stacks():
        realizations: list[Realization] = []

        for variation in variations:
            realized, pulled, refusals = realize(
                variation.trail,
                slices.sampling if slices else None,
                bench.facts_of(stack),
                stack.trail.serving,
            )
            realizations.append(
                Realization(
                    variation=variation.name,
                    reasoning=reasoning_of(realized),
                    sampling=sampling_of(pulled),
                    refusals=refusals_of(refusals),
                )
            )

        stacks.append(
            StackRealizations(
                stack=stack.name,
                owner=stack.owner.name,
                current=bench.cell.stack is not None
                and bench.cell.stack.name == stack.name,
                realizations=realizations,
            )
        )

    return ReasoningTable(
        sampling=None
        if slices is None
        else maybe_ref_of(bench, "sampling", slices.sampling),
        variations=[
            ReasoningVariation(
                name=variation.name,
                owner=variation.owner.name,
                fingerprint=variation.trail.fingerprint,
                effort=variation.trail.effort,
                budget=variation.trail.budget,
                current=slices is not None and _same(slices.reasoning, variation.trail),
            )
            for variation in variations
        ],
        stacks=stacks,
    )


@router.get("/scorers", response=list[ScorerOut])
def scorers(request: HttpRequest, cell: Query[CellIn]):
    """The scorers, what each reads, and whether the cell's output offers it."""
    bench = held(request, cell)
    offered = bench.cell.slices.output.views if bench.cell.configuration else None

    return [
        ScorerOut(
            name=scorer.name,
            owner=scorer.owner,
            fingerprint=scorer.trail.fingerprint,
            function=scorer.trail.function,
            view=scorer.view,
            target_kind=scorer.target_kind,
            args=scorer.args,
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

    model = get_visible_branch_model("configuration", bench.identity, cell.name)

    return Saved(
        what=saved.what,
        copied=saved.copied,
        configuration=branches_of(bench, "configuration", [model])[0],
    )


@router.get("/cell/{entity}", response=BranchDetail)
def show_part(request: HttpRequest, entity: EntityName, cell: Query[CellIn]):
    """The cell's ENTITY, and what came of the identity's runs with it."""
    bench = held(request, cell)
    return detail_of(bench, entity, _in_cell(bench, cell, entity))


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
    elif entity == "stack" or entity in STACK_PARTS:
        if cell.stack is None or bench.cell.stack is None:
            raise HttpError(400, "the cell has no stack")

        if entity == "stack":
            return get_visible_branch_model("stack", bench.identity, cell.stack)

        trail = getattr(bench.cell.stack.trail, entity)
    else:
        raise HttpError(400, f"a {entity} isn't in the cell")

    if trail is None:
        raise HttpError(404, f"the cell has no {entity}")

    return get_visible_branch_model(entity, bench.identity, trail=trail.id)


def _same(trail: Any, other: Any) -> bool:
    return trail.fingerprint == other.fingerprint
