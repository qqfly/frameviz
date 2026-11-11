import { FrameVizCore, applySceneSnapshot } from '@frameviz/core';
import { Quaternion, Vector3 } from 'three';

type Keyframe = {
  time: number;
  pose: { position: [number, number, number]; quaternion: [number, number, number, number] };
};

function interpolate(keys: Keyframe[], time: number) {
  if (time <= keys[0].time) return keys[0].pose;
  if (time >= keys[keys.length - 1].time) return keys[keys.length - 1].pose;
  let low = 0;
  let high = keys.length - 1;
  while (high - low > 1) {
    const index = Math.floor((low + high) / 2);
    if (keys[index].time > time) high = index;
    else low = index;
  }
  const start = keys[low];
  const end = keys[high];
  const amount = (time - start.time) / (end.time - start.time);
  return {
    position: new Vector3(...start.pose.position).lerp(new Vector3(...end.pose.position), amount).toArray(),
    quaternion: new Quaternion(...start.pose.quaternion).slerp(new Quaternion(...end.pose.quaternion), amount).toArray(),
  };
}

const data = JSON.parse(document.getElementById('frameviz-data')!.textContent!);
const container = document.getElementById('viewer')!;
const status = document.getElementById('status')!;
const player = document.getElementById('player')!;
const play = document.getElementById('play') as HTMLButtonElement;
const seek = document.getElementById('seek') as HTMLInputElement;
const timeLabel = document.getElementById('time')!;
const core = new FrameVizCore({
  container, keyboardShortcuts: false,
  overlay: document.getElementById('overlay')!,
});
applySceneSnapshot(core, data.snapshot);
new ResizeObserver(() => core.resize()).observe(container);

const tracks = Object.entries(data.animation) as [string, Keyframe[]][];
const duration = Math.max(0, ...tracks.map(([, keys]) => keys[keys.length - 1].time));
let playing = false;
let time = 0;
let lastFrame: number | undefined;
let ready = false;

function showTime() {
  seek.value = String(time);
  timeLabel.textContent = `${time.toFixed(2)} / ${duration.toFixed(2)} s`;
  core.handleCommand('set_object_transforms', {
    items: tracks.map(([handle, keys]) => ({ handle, pose: interpolate(keys, time) })),
  });
}

function setPlaying(value: boolean) {
  playing = value;
  lastFrame = undefined;
  play.textContent = playing ? 'Pause' : 'Play';
}

play.addEventListener('click', () => {
  if (!playing && time >= duration) time = 0;
  setPlaying(!playing);
  showTime();
});
seek.addEventListener('input', () => {
  time = seek.valueAsNumber;
  lastFrame = undefined;
  showTime();
});

function frame(now: number) {
  if (!ready) {
    const state = core.getRenderStatus();
    if (state.failed.length) {
      status.textContent = 'Unable to load a model in this tutorial.';
      return;
    }
    if (state.ready) {
      ready = true;
      status.hidden = true;
      if (duration > 0) {
        seek.max = String(duration);
        player.hidden = false;
        core.resize();
      }
      showTime();
    }
  }
  if (playing) {
    if (lastFrame !== undefined) time = Math.min(duration, time + (now - lastFrame) / 1000);
    lastFrame = now;
    if (time >= duration) setPlaying(false);
    showTime();
  }
  core.render();
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
