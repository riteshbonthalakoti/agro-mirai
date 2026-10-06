import { clampZoom, fieldCameraStop, MIN_ZOOM, MAX_ZOOM, FIELD_ZOOM } from './mapCamera';

describe('clampZoom', () => {
  it('passes through values inside range', () => {
    expect(clampZoom(10)).toBe(10);
  });

  it('clamps below MIN_ZOOM', () => {
    expect(clampZoom(0)).toBe(MIN_ZOOM);
  });

  it('clamps above MAX_ZOOM', () => {
    expect(clampZoom(99)).toBe(MAX_ZOOM);
  });
});

describe('fieldCameraStop', () => {
  it('builds a center/zoom stop from lat/lon', () => {
    const stop = fieldCameraStop(12.34, 56.78);
    expect(stop.center).toEqual([56.78, 12.34]);
    expect(stop.zoom).toBe(FIELD_ZOOM);
  });

  it('uses a custom zoom when provided', () => {
    const stop = fieldCameraStop(12.34, 56.78, 18);
    expect(stop.zoom).toBe(18);
  });

  it('clamps an out-of-range custom zoom', () => {
    const stop = fieldCameraStop(12.34, 56.78, 999);
    expect(stop.zoom).toBe(MAX_ZOOM);
  });
});
