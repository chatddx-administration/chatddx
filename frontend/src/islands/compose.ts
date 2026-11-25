import { mount } from "svelte";
import type { Props } from "$lib/compose/props";
import Breakdown from "$lib/compose/Breakdown.svelte";
import { Following } from "$lib/compose/following.svelte";
import Preview from "$lib/compose/Preview.svelte";
import { Sending } from "$lib/compose/sending.svelte";
import Compose from "./Compose.svelte";

const target = document.getElementById("compose");
const held = document.getElementById("compose-props");
const given = held ? (JSON.parse(held.textContent ?? "null") as Props) : null;
const following = new Following(
  given?.baseline?.runs ?? [],
  given?.baseline?.running ?? false,
  given?.baseline?.whole ?? false,
);
const grid = document.querySelector<HTMLElement>("[data-compose]");
const column = document.getElementById("compose-preview");
if (target && held) {
  const props = JSON.parse(held.textContent ?? "null") as Props;
  const sending = new Sending((open) => {
    if (!grid || !column) return;
    grid.toggleAttribute("data-slid", open);
    column.inert = !open;
    if (open && !matchMedia("(width >= 80rem)").matches) {
      column.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
  target.replaceChildren();
  mount(Compose, { target, props: { held: props, sending, following } });
  if (column && props.drafted) {
    mount(Preview, {
      target: column,
      props: { thread: props.configuration.id, own: props.configuration.language, sending },
    });
  }
}

const breakdown = document.querySelector("#compose-breakdown > .pane");
if (breakdown && held) {
  const props = JSON.parse(held.textContent ?? "null") as Props;
  breakdown.replaceChildren();
  mount(Breakdown, {
    target: breakdown,
    props: {
      thread: props.configuration.id,
      version: props.versions.findIndex((v) => v.id === props.head) + 1,
      following,
    },
  });
}
