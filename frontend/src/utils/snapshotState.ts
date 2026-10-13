import type {Point, Snapshot} from '../types';

export type SnapshotSource = 'http' | 'websocket';

function shareData(previous: Snapshot, next: Snapshot): Snapshot {
  const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
  for (const key of ['scene', 'calibration', 'settings', 'video'] as const) {
    if (equal(previous[key], next[key])) Object.assign(next, {[key]: previous[key]});
  }
  const before = previous.history, after = next.history;
  if (previous.run_id === next.run_id && before?.length === after?.length && equal(before?.at(-1), after?.at(-1))) next.history = before;
  if (next.metrics && previous.metrics && equal(next.metrics.vehicle_types, previous.metrics.vehicle_types)) {
    next.metrics = {...next.metrics, vehicle_types: previous.metrics.vehicle_types};
  }
  return next;
}

export class SnapshotGate {
  current: Snapshot | null = null;
  private retired = new Set<string>();
  accept(incoming: Snapshot, source: SnapshotSource): Snapshot | null {
    const previous = this.current;
    if (previous) {
      if (incoming.session_id !== previous.session_id) {
        if (source !== 'websocket' || this.retired.has(incoming.session_id)) return previous;
        this.retired.add(previous.session_id);
      } else if (incoming.revision <= previous.revision) return previous;
    }
    const next = {...incoming};
    this.current = previous && previous.session_id === next.session_id ? shareData(previous, next) : next;
    return this.current;
  }
}

export interface DecodedFrame {snapshot: Snapshot; image: HTMLImageElement | null}

export class FrameDecoder {
  private generation = 0;
  private current: DecodedFrame | null = null;
  constructor(private commit: (frame: DecodedFrame) => void,
              private fail: () => void = () => {},
              private createImage: () => HTMLImageElement = () => new Image()) {}
  update(snapshot: Snapshot) {
    const generation = ++this.generation;
    if (!snapshot.image) {
      this.current = {snapshot, image: null};
      this.commit(this.current);
      return;
    }
    if (this.current?.snapshot.image === snapshot.image && this.current.snapshot.video_token === snapshot.video_token) {
      this.current = {...this.current, snapshot};
      this.commit(this.current);
      return;
    }
    const image = this.createImage();
    image.onload = () => {
      if (generation !== this.generation) return;
      this.current = {snapshot, image};
      this.commit(this.current);
    };
    image.onerror = () => {if (generation === this.generation) this.fail();};
    image.src = snapshot.image;
  }
  cancel() {this.generation++;}
}

export function appendDrawPoint(points: Point[], point: Point): Point[] {
  const previous = points.at(-1);
  return previous && Math.hypot(previous[0]-point[0], previous[1]-point[1]) < 1 ? points : [...points, point];
}
