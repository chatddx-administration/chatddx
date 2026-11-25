import { api, why } from "$lib/api/client";
import { type Followed, open, whole } from "./baseline";

// Policy: each run of the baseline is read again so long after while any is open, rather than a stream held open for
// each, as only how far it has come is shown here.
const AGAIN = 5_000;

export class Following {
  runs = $state<Followed[]>([]);
  running = $state(false);
  whole = $state(false);
  ended = $state(false);
  problem = $state<string | null>(null);
  private readonly ids: string[];

  constructor(ids: string[], running: boolean, wholeNow: boolean) {
    this.ids = ids;
    this.running = running;
    this.whole = wholeNow;
    if (running && ids.length) void this.read();
  }

  private async read(): Promise<void> {
    const got = await Promise.all(this.ids.map((run) => api.GET("/api/runs/{run}", { params: { path: { run } } })));
    const failed = got.find((r) => !r.data);
    if (failed) {
      this.problem = why(failed.error);
      return;
    }
    this.runs = got.map((r) => r.data as Followed);
    this.running = this.runs.some(open);
    if (this.running) setTimeout(() => void this.read(), AGAIN);
    else {
      this.whole = whole(this.runs);
      this.ended = true;
    }
  }
}
