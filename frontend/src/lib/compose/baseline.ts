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
    case "queued": {
      const said = [
        t("queued"),
        job.ahead === null ? t("paused") : tn("%(num)s ahead", "%(num)s ahead", job.ahead, { num: job.ahead }),
      ];
      if (job.halt) said.push(t("halting"));
      return said.join(", ");
    }
    case "under way":
      if (job.halt) return t("halting");
      return run.finished ? tp("in progress", "scoring") : tp("in progress", "sending");
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
