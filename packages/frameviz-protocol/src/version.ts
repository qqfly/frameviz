import { PROTOCOL_VERSION } from './constants.js';

export function parseProtocolVersion(value: unknown): number[] | null {
  if (typeof value !== 'string' || !/^(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})$/.test(value)) return null;
  return value.split('.').map(Number);
}

export function isProtocolCompatible(remote: unknown, local: string = PROTOCOL_VERSION): boolean {
  const a = parseProtocolVersion(remote), b = parseProtocolVersion(local);
  return !!a && !!b && a[0] === b[0] && a[1] === b[1];
}

export function hostVersionError(remote: unknown, local: string = PROTOCOL_VERSION): string | null {
  const a = parseProtocolVersion(remote), b = parseProtocolVersion(local);
  if (!a || !b) return 'Missing or malformed protocol version; install matching FrameViz runtime and SDK/Viewer.';
  if (a[0] === b[0] && a[1] === b[1]) return null;
  if (a[0] < b[0] || (a[0] === b[0] && a[1] < b[1])) return `Host protocol ${remote} is older than client ${local}. Upgrade the FrameViz runtime.`;
  return `Host protocol ${remote} is newer than client ${local}. Upgrade the SDK/Viewer.`;
}
