import type { Schemas } from "$lib/api/client";
import { t, tn, tp } from "$lib/locale";

export type Followed = Schemas["RunDetail"];

export function open(run: Followed): boolean {
  return run.job?.status === "queued" || run.job?.status === "under way";
}

export function whole(runs: Followed[]): boolean {
  return runs.length > 0 && runs.every((r) => r.finished && r.job?.status === "finished");
}

export function tally(runs: Followed[]): { ended: number; of: number } {
  return {
    ended: runs.reduce((n, r) => n + Math.min(r.items.length, r.cases.length * r.seeds.length), 0),
    of: runs.reduce((n, r) => n + r.cases.length * r.seeds.length, 0),
  };
}

export function said(run: Followed): string {
  const job = run.job;
  if (job === null || job === undefined) return run.finished ? tp("job", "finished") : "—";
  switch (job.status) {
    case "queued":
      if (job.ahead === null) return job.halt ? t("queued, paused, halting") : t("queued, paused");
      return job.halt
        ? tn("queued, %(num)s ahead, halting", "queued, %(num)s ahead, halting", job.ahead, { num: job.ahead })
        : tn("queued, %(num)s ahead", "queued, %(num)s ahead", job.ahead, { num: job.ahead });
    case "under way":
      if (job.halt) return t("halting");
      return run.finished ? tp("a run under way", "Scoring") : tp("a run under way", "Sending");
    default: {
      const status = {
        finished: tp("job", "finished"),
        stopped: tp("job", "stopped"),
        failed: tp("job", "failed"),
      }[job.status];
      return job.why ? t("%(status)s: %(why)s", { status, why: job.why }) : status;
    }
  }
}
