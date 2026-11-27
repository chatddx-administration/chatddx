import type { Schemas } from "$lib/api/client";
import { t, tp } from "$lib/locale";
import type { Event } from "./events";

export type Kind = Schemas["ItemDeltaData"]["kind"];

export type Item = {
  case: string;
  replicate: number;
  phase: "waiting" | "sending" | "ended";
  kind: Kind | null;
  tokens: number;
  text: Record<Kind, string>;
  tools: number;
  outcome: Schemas["Outcome"] | null;
  why: string | null;
  sent: number;
  received: number;
};

export type Scoring = {
  scorer: string;
  name: string;
  score: string | null;
  views: number;
  scored: number;
  asked: number;
  answered: number;
};

export type Progress = {
  started: Schemas["RunStartedData"] | null;
  items: Item[];
  noted: Schemas["Finding"][];
  finished: Schemas["RunFinishedData"] | null;
  scorings: Scoring[];
  scores: Schemas["Graded"][] | null;
  errors: string[];
  done: Schemas["DoneData"] | null;
};

export function begun(): Progress {
  return {
    started: null,
    items: [],
    noted: [],
    finished: null,
    scorings: [],
    scores: null,
    errors: [],
    done: null,
  };
}

function item(progress: Progress, at: { case: string; replicate: number }): Item {
  let found = progress.items.find((i) => i.case === at.case && i.replicate === at.replicate);
  if (found === undefined) {
    found = {
      case: at.case,
      replicate: at.replicate,
      phase: "waiting",
      kind: null,
      tokens: 0,
      text: { reasoning: "", content: "", tool_call: "" },
      tools: 0,
      outcome: null,
      why: null,
      sent: 0,
      received: 0,
    };
    progress.items.push(found);
  }
  return found;
}

function scoring(progress: Progress, scorer: string): Scoring | undefined {
  return progress.scorings.find((s) => s.scorer === scorer);
}

export function fold(progress: Progress, name: Event, data: unknown): void {
  switch (name) {
    case "run.started": {
      const started = data as Schemas["RunStartedData"];
      progress.started = started;
      for (const c of started.cases) {
        for (const replicate of started.seeds.keys()) item(progress, { case: c, replicate });
      }
      break;
    }
    case "item.started":
      item(progress, data as Schemas["ItemStartedData"]).phase = "sending";
      break;
    case "item.delta": {
      const delta = data as Schemas["ItemDeltaData"];
      const found = item(progress, delta);
      found.phase = "sending";
      found.kind = delta.kind;
      found.tokens = delta.tokens;
      found.text[delta.kind] += delta.text;
      break;
    }
    case "item.tool":
      item(progress, data as Schemas["ItemToolData"]).tools += 1;
      break;
    case "item.ended": {
      const ended = data as Schemas["ItemEndedData"];
      const found = item(progress, ended);
      found.phase = "ended";
      found.kind = null;
      found.outcome = ended.outcome;
      found.why = ended.why;
      found.sent = ended.prompt_tokens;
      found.received = ended.completion_tokens;
      break;
    }
    case "run.noted":
    case "score.noted":
      progress.noted.push(data as Schemas["Finding"]);
      break;
    case "run.finished":
      progress.finished = data as Schemas["RunFinishedData"];
      break;
    case "run.scoring":
      for (const s of (data as Schemas["ScoringData"]).scorers) {
        if (!scoring(progress, s.scorer)) {
          progress.scorings.push({ ...s, score: null, views: 0, scored: 0, asked: 0, answered: 0 });
        }
      }
      break;
    case "score.started": {
      const started = data as Schemas["ScoreStartedData"];
      let found = scoring(progress, started.scorer);
      if (!found) {
        found = { scorer: started.scorer, name: started.name, score: null, views: 0, scored: 0, asked: 0, answered: 0 };
        progress.scorings.push(found);
      }
      found.score = started.score;
      found.views = started.labels.length;
      break;
    }
    case "score.item": {
      const scored = data as Schemas["ScoreItemData"];
      const found = progress.scorings.find((s) => s.score === scored.score);
      if (found) found.scored += 1;
      break;
    }
    case "judge.asked": {
      const found = scoring(progress, (data as Schemas["JudgeAskedData"]).scorer);
      if (found) found.asked += 1;
      break;
    }
    case "judge.answered": {
      const found = [...progress.scorings].reverse().find((s) => s.score !== null);
      if (found) found.answered += 1;
      break;
    }
    case "run.scored":
      progress.scores = (data as Schemas["RunScoredData"]).scores;
      break;
    case "error":
      progress.errors.push((data as Schemas["ErrorData"]).detail);
      break;
    case "done":
      progress.done = data as Schemas["DoneData"];
      break;
    default:
      break;
  }
}

export function tally(progress: Progress): {
  ended: number;
  of: number;
  outcomes: [Schemas["Outcome"], number][];
} {
  const counted = new Map<Schemas["Outcome"], number>();
  for (const i of progress.items) {
    if (i.outcome !== null) counted.set(i.outcome, (counted.get(i.outcome) ?? 0) + 1);
  }
  return {
    ended: progress.items.filter((i) => i.phase === "ended").length,
    of: progress.items.length,
    outcomes: [...counted],
  };
}

export function failed(progress: Progress): string | null {
  if (progress.errors.length) return progress.errors.join("; ");
  return progress.finished === null ? t("the run didn't finish") : null;
}

export function streaming(kind: Kind | null): string {
  if (kind === "reasoning") return tp("in progress", "thinking");
  if (kind === "tool_call") return tp("in progress", "calling a tool");
  return tp("in progress", "writing");
}
