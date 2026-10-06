export const MIN_ZOOM = 2;
export const MAX_ZOOM = 20;
export const FIELD_ZOOM = 14;

export function clampZoom(zoom: number): number {
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom));
}

export function fieldCameraStop(lat: number, lon: number, zoom: number = FIELD_ZOOM) {
  return {
    center: [lon, lat] as [number, number],
    zoom: clampZoom(zoom),
  };
}
