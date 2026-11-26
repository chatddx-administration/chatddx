import type { Schemas } from "$lib/api/client";
import type { Listed } from "./cases";
import type { Drafted } from "./drafting";

export type Facts = {
  levels: Record<string, { lands?: string; nearest?: string[]; refused?: string }>;
  recommended: Record<string, Record<string, number>>;
  output: Record<string, { refused?: string; note?: string | null }>;
  answers: string | null;
  budget: boolean | string;
};

export type ToolChoice = { digest: string; name: string; description: string };

export type Props = {
  configuration: Schemas["ThreadDetail"];
  me: string;
  versions: Schemas["Versioned"][];
  head: number;
  varied: boolean;
  modelChoices: Schemas["Thread"][];
  facts: Record<string, Facts | null>;
  toolChoices: ToolChoice[];
  drafted: Drafted | null;
  configurations: Schemas["Thread"][];
  cases: Listed[];
  baseline: { running: boolean; behind: boolean; whole: boolean; runs: string[] } | null;
};
