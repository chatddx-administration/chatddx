import createClient from "openapi-fetch";
import { refusal, t, upFirst, whoops } from "$lib/locale";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];

export const api = createClient<paths>();

function titled(code: Schemas["Error"]["code"] | undefined): string {
  const titles: Partial<Record<Schemas["Error"]["code"], string>> = {
    not_found: upFirst(t("not found")),
    not_allowed: upFirst(t("not allowed")),
    cross_site: upFirst(t("not allowed")),
    unauthenticated: t("Sign in"),
    refused: upFirst(t("can't be done")),
    unprocessable: upFirst(t("can't be done")),
    conflict: upFirst(t("can't be done")),
    moved_on: upFirst(t("newer version")),
    ambiguous: upFirst(t("can't be done")),
    over_quota: upFirst(t("can't be done")),
  };
  return (code && titles[code]) ?? upFirst(t("something went wrong"));
}

// Policy: what a person can cause is worded, and what isn't worded they couldn't have
// caused, so it is passed on as it is.
export function why(error: unknown): string {
  const failure = error as Partial<Schemas["Error"]> | undefined;
  const detail = failure?.detail;
  if (typeof detail === "string" && failure?.code === "whoops") {
    return `${whoops(detail)} ${t("Copy this and send it to drift@chatddx.com:")} ${failure.pass_on ?? ""}`;
  }
  if (typeof detail === "string" && failure?.wording) return refusal(detail, failure.wording, failure.params ?? {});
  if (detail === undefined) return `${upFirst(t("something went wrong"))}.`;
  const passed = typeof detail === "string" ? detail : detail.map((d) => JSON.stringify(d)).join("; ");
  return `${titled(failure?.code)}. ${t("Copy this and send it to drift@chatddx.com:")} ${passed}`;
}
