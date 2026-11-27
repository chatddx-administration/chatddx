import { mount, unmount } from "svelte";
import {
  type Editing,
  type Editor,
  betweenBrackets,
  inBrackets,
  labelled,
  misread,
  read,
  segsOf,
  textOfSegs,
  written,
} from "$lib/library/editors";
import SchemaInput from "$lib/library/SchemaInput.svelte";
import { t } from "$lib/locale";
import TextsField from "$lib/library/TextsField.svelte";
import ViewsField from "$lib/library/ViewsField.svelte";
import type { ScorerView } from "$lib/scorer/scorers";

type Shown = ReturnType<typeof mount>;
type Drawable = Exclude<Editor, { as: "json" }>;
type Drawn = { draw: (target: HTMLElement) => Shown; raw: HTMLElement[] } | string;

const held = document.getElementById("library-props");
if (held) {
  const editing = JSON.parse(held.textContent ?? "null") as Editing;
  for (const editor of editing.fields) {
    if (editor.as === "json") checked(editor.name, editor.brackets);
    else enhanced(editor, editing);
  }
  const form = document.querySelector<HTMLFormElement>("form[data-checked]");
  if (form) gated(form);
}

// Policy: a library form is read as it is typed as the server reads it when it is sent,
// and isn't sent while it would be refused, rather than coming back refused.
function gated(form: HTMLFormElement): void {
  const note = document.createElement("ul");
  note.className = "space-y-0.5 text-xs text-warning";
  note.hidden = true;
  const sending = [...form.querySelectorAll<HTMLButtonElement>("button:not([type=button])")];
  (sending[0]?.parentElement ?? form).before(note);
  let asked = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const check = async (): Promise<void> => {
    const mine = ++asked;
    const body = new FormData(form);
    body.set("checking", "1");
    const got = await fetch(form.action, { method: "POST", body });
    if (mine !== asked || !got.ok) return;
    const { refused } = (await got.json()) as { refused: string[] };
    note.replaceChildren(...refused.map((r) => Object.assign(document.createElement("li"), { textContent: r })));
    note.hidden = refused.length === 0;
    for (const b of sending) b.disabled = refused.length > 0;
  };
  const later = (): void => {
    clearTimeout(timer);
    timer = setTimeout(() => void check(), 400);
  };
  form.addEventListener("input", later);
  form.addEventListener("change", later);
  void check();
}

function wrote(area: HTMLTextAreaElement, text: string): void {
  area.value = text;
  area.dispatchEvent(new Event("input", { bubbles: true }));
}

// Policy: a JSON box says as it is typed in what keeps it from being sent, and the form
// isn't sent while it does, rather than coming back refused.
function checked(name: string, brackets: string | null): void {
  const area = document.querySelector<HTMLTextAreaElement>(`textarea[name="f.${name}"]`);
  if (!area) return;
  const note = document.createElement("p");
  note.className = "mt-1 text-xs text-warning";
  note.hidden = true;
  area.after(note);
  const refusal = (): string | null => {
    const found = misread(area.value, brackets);
    note.textContent = found ?? "";
    note.hidden = found === null;
    area.setAttribute("aria-invalid", String(found !== null));
    return found;
  };
  area.addEventListener("input", refusal);
  area.form?.addEventListener("submit", (sent) => {
    if (refusal() === null) return;
    sent.preventDefault();
    area.focus();
  });
}

function picked(name: string, editing: Editing): string {
  const select = document.querySelector<HTMLSelectElement>(`select[name="f.${name}"]`);
  if (select) return select.value;
  const given = editing.held[name];
  return typeof given === "string" ? given : "";
}

function following(editor: Drawable): string[] {
  if (editor.as === "texts") return Object.keys(editor.slots).length ? ["purpose"] : [];
  return editor.as === "views" || editor.of ? [editor.of ?? ""] : [];
}

// Policy: the text box stays the form's, so that it posts as it does without scripts; an editor writes into it only
// what is changed in it, so that a form sent as it is writes nothing.
function enhanced(editor: Drawable, editing: Editing): void {
  const area = document.querySelector<HTMLTextAreaElement>(`textarea[name="f.${editor.name}"]`);
  if (!area) return;
  const as = document.querySelector<HTMLSelectElement>(`select[name="as.${editor.name}"]`);
  const box = document.createElement("div");
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "mt-1 text-xs text-primary hover:underline";
  const note = document.createElement("p");
  note.className = "mt-1 text-xs text-warning";
  (as ?? area).before(box);
  area.after(toggle, note);
  let shown: Shown | null = null;
  let raw: HTMLElement[] = [area, ...(as ? [as] : [])];

  const opened = (): string | null => {
    const made = drawn(editor, editing, area, as);
    if (typeof made === "string") return made;
    if (shown) void unmount(shown);
    box.replaceChildren();
    shown = made.draw(box);
    raw = made.raw;
    for (const r of raw) r.hidden = true;
    box.hidden = false;
    toggle.textContent = t("Write it as JSON");
    note.hidden = true;
    return null;
  };
  const closed = (why: string | null): void => {
    if (shown) void unmount(shown);
    shown = null;
    box.hidden = true;
    for (const r of raw) r.hidden = false;
    toggle.textContent = t("Back to the form");
    note.textContent = why ?? "";
    note.hidden = why === null;
  };

  const tried = (): void => {
    const why = opened();
    if (why !== null) closed(why);
  };

  toggle.addEventListener("click", () => (shown ? closed(null) : tried()));
  tried();
  for (const name of following(editor)) {
    document.querySelector(`select[name="f.${name}"]`)?.addEventListener("change", () => {
      if (shown || !note.hidden) tried();
    });
  }
}

function drawn(editor: Drawable, editing: Editing, area: HTMLTextAreaElement, as: HTMLSelectElement | null): Drawn {
  const raw = [area, ...(as ? [as] : [])];
  switch (editor.as) {
    case "texts": {
      const segs = segsOf(as?.value === "text" ? area.value : inBrackets(area), as ? as.value === "text" : null);
      if (!segs) return t("What it holds isn't JSON the form can show: set it right here first.");
      const slots = editor.slots[picked("purpose", editing)] ?? [];
      const changed = (s: Parameters<typeof textOfSegs>[0]): void => {
        const made = textOfSegs(s, as !== null);
        if (as) as.value = made.asText ? "text" : "json";
        wrote(area, made.asText ? made.text : betweenBrackets(area, made.text));
      };
      const label = editor.name.replaceAll("_", " ");
      return {
        draw: (target) =>
          mount(TextsField, { target, props: { segs, slots, inserts: editor.inserts, label, changed } }),
        raw,
      };
    }
    case "schema": {
      const schema = editor.schema ?? editing.schemas[picked(editor.of ?? "", editing)];
      if (!schema) return t("Pick its expectation schema first, and the form shows what it holds.");
      const found = area.value.trim() ? read(inBrackets(area)) : { ok: true as const, value: null };
      if (!found.ok) return t("What it holds isn't JSON the form can show: set it right here first.");
      const changed = (v: unknown): void => {
        wrote(area, betweenBrackets(area, written(v)));
      };
      const label = editor.name.replaceAll("_", " ");
      return {
        draw: (target) => mount(SchemaInput, { target, props: { schema, value: found.value, label, changed } }),
        raw,
      };
    }
    case "views": {
      const scoring = editing.scoring;
      const found = area.value.trim() ? read(inBrackets(area)) : { ok: true as const, value: [] };
      if (!scoring || !found.ok || !Array.isArray(found.value)) {
        return t("What it holds isn't JSON the form can show: set it right here first.");
      }
      const views = found.value as ScorerView[];
      const naming = document.querySelector<HTMLTextAreaElement>('textarea[name="labels"]');
      const given = naming ? read(naming.value) : null;
      const { views: labels, rest } = labelled(given?.ok ? given.value : null, views.length);
      const was = written([views, labels]);
      let touched = false;
      const schema = editing.schemas[picked(editor.of, editing)] ?? null;
      const changed = (now: ScorerView[], named: string[]): void => {
        touched ||= written([now, named]) !== was;
        if (!touched) return;
        wrote(area, betweenBrackets(area, written(now)));
        if (naming) naming.value = written({ ...rest, views: named });
      };
      const shown = naming?.closest("label");
      return {
        draw: (target) => mount(ViewsField, { target, props: { views, labels, schema, scoring, changed } }),
        raw: [...raw, ...(shown ? [shown] : [])],
      };
    }
  }
}
