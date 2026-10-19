import type {TrafficEvent} from '../types';

export const SOUND_KEY = 'tunnel-twin-alert-sound';
type StorageLike = Pick<Storage, 'getItem' | 'setItem'> | null | undefined;

export function readSoundPreference(storage: StorageLike = globalThis.localStorage): boolean {
  try {
    const value = storage?.getItem(SOUND_KEY);
    return value === null || value === undefined ? true : value === '1';
  } catch {
    return true;
  }
}

export function writeSoundPreference(on: boolean, storage: StorageLike = globalThis.localStorage): void {
  try {
    storage?.setItem(SOUND_KEY, on ? '1' : '0');
  } catch {
    // Private mode or a blocked storage backend must not break alerting.
  }
}

export function eventKey(event: TrafficEvent): string {
  return event.event_id || `${event.run_id || ''}:${event.timestamp}:${event.vehicle_id}:${event.event}`;
}

export function unseenEvents(seen: Set<string>, events: TrafficEvent[]): TrafficEvent[] {
  return events.filter(event => !seen.has(eventKey(event)));
}

let audio: AudioContext | null = null;

export function primeAlertAudio(): void {
  try {
    const AudioContextClass = globalThis.AudioContext || (globalThis as unknown as {webkitAudioContext?: typeof AudioContext}).webkitAudioContext;
    if (!AudioContextClass) return;
    if (!audio) audio = new AudioContextClass();
    if (audio.state === 'suspended') void audio.resume();
  } catch {
    // Audio is optional; some browsers block it until the next user gesture.
  }
}

export function playAlertTone(): void {
  try {
    primeAlertAudio();
    if (!audio) return;
    const now = audio.currentTime;
    const oscillator = audio.createOscillator();
    const gain = audio.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(880, now);
    oscillator.frequency.setValueAtTime(660, now + .16);
    gain.gain.setValueAtTime(.0001, now);
    gain.gain.exponentialRampToValueAtTime(.18, now + .02);
    gain.gain.exponentialRampToValueAtTime(.0001, now + .38);
    oscillator.connect(gain);
    gain.connect(audio.destination);
    oscillator.start(now);
    oscillator.stop(now + .4);
  } catch {
    // Never block the event UI when audio hardware or permissions fail.
  }
}
