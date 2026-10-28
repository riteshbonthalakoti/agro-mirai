import React, { useEffect, useMemo, useRef, useState } from 'react';
import { StyleSheet, TouchableOpacity, View, Text } from 'react-native';
import Svg, { Path, Circle as SvgCircle } from 'react-native-svg';
let Map: any = View;
let Camera: any = View;
let Marker: any = View;
let ShapeSource: any = null;
let FillLayer: any = null;
let LineLayer: any = null;
let hasMapLibre = false;

try {
  const ML = require('@maplibre/maplibre-react-native');
  if (ML && (ML.Map || ML.MapView)) {
    Map = ML.Map || ML.MapView;
    Camera = ML.Camera;
    Marker = ML.Marker;
    ShapeSource = ML.ShapeSource;
    FillLayer = ML.FillLayer;
    LineLayer = ML.LineLayer;
    hasMapLibre = true;
  }
} catch {
  hasMapLibre = false;
}
type CameraRef = any;

/** Classic red map-pin teardrop, same silhouette as Google Maps' default
 *  marker: a circle with a point tangent at the bottom, which is where
 *  the exact coordinate sits -- the Marker's anchor is 'bottom' so this
 *  tip, not the circle's center, is what's pinned to field lat/lon. */
function RedPin({ size = 40 }: { size?: number }) {
  return (
    <Svg width={size} height={size * 1.25} viewBox="0 0 32 40" fill="none">
      <Path
        d="M16 0C7.163 0 0 7.163 0 16c0 11 16 24 16 24s16-13 16-24c0-8.837-7.163-16-16-16z"
        fill="#EA4335"
        stroke="#B31412"
        strokeWidth={1}
      />
      <SvgCircle cx={16} cy={16} r={6} fill="#fff" />
    </Svg>
  );
}

/** Generates a GeoJSON polygon approximating a circle of `radiusM` metres
 *  around (lat, lon) -- the field's acreage drawn as a boundary, the same
 *  "point + radius" approach any mapping library uses when there's no
 *  surveyed polygon, just a center and an area. 64 points is smooth enough
 *  at any zoom level a phone screen shows a single field at. */
function circlePolygon(lat: number, lon: number, radiusM: number, points = 64) {
  const coords: [number, number][] = [];
  const latRad = (lat * Math.PI) / 180;
  const metersPerDegLat = 111320;
  const metersPerDegLon = 111320 * Math.cos(latRad);
  for (let i = 0; i <= points; i++) {
    const angle = (i / points) * 2 * Math.PI;
    const dLat = (radiusM * Math.sin(angle)) / metersPerDegLat;
    const dLon = (radiusM * Math.cos(angle)) / metersPerDegLon;
    coords.push([lon + dLon, lat + dLat]);
  }
  return {
    type: 'Feature' as const,
    properties: {},
    geometry: { type: 'Polygon' as const, coordinates: [coords] },
  };
}

/** Area (hectares) -> radius (metres) of a circle of that area -- the
 *  "assume the pin is the center, radius big enough for the farmer's
 *  acreage" field-boundary approximation. 1 ha = 10,000 m²; r = √(A/π). */
function radiusFromHectares(areaHa: number): number {
  const areaM2 = areaHa * 10000;
  return Math.sqrt(areaM2 / Math.PI);
}
import * as Location from 'expo-location';
import { isOnline } from '../api';
import { useApp } from '../ctx';
import { Icon } from '../../icons';
import { C, S } from '../theme';
import { Banner } from '../ui';
import { fieldCameraStop } from '../mapCamera';

// ESRI World Imagery: free, no API key, Web Mercator XYZ — compatible with MapLibre
const ESRI_SATELLITE_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

// MapLibre style with satellite raster tiles
const SATELLITE_STYLE = {
  version: 8 as const,
  sources: {
    esri: {
      type: 'raster' as const,
      tiles: [ESRI_SATELLITE_URL],
      tileSize: 256,
      attribution: '© Esri, Maxar, Earthstar Geographics',
    },
  },
  layers: [
    {
      id: 'background',
      type: 'background' as const,
      paint: { 'background-color': '#1a1a2e' },
    },
    {
      id: 'satellite-layer',
      type: 'raster' as const,
      source: 'esri',
      paint: { 'raster-opacity': 1 },
    },
  ],
};

export function FieldMapScreen({ onClose }: { onClose: () => void }) {
  const { field, t } = useApp();
  const [userLocation, setUserLocation] = useState<{ lat: number; lon: number } | null>(null);
  const [activeFocus, setActiveFocus] = useState<'phone' | 'field'>('phone');
  const online = isOnline();
  const cameraRef = useRef<CameraRef>(null);

  // Get current location on mount and immediately fly to phone's location
  useEffect(() => {
    let isMounted = true;
    const getLocation = async () => {
      try {
        const perm = await Location.requestForegroundPermissionsAsync();
        if (perm.status === 'granted') {
          const last = await Location.getLastKnownPositionAsync();
          if (last && isMounted) {
            const coords = { lat: last.coords.latitude, lon: last.coords.longitude };
            setUserLocation(coords);
            cameraRef.current?.easeTo({ center: [coords.lon, coords.lat], zoom: 15, duration: 600 });
          }
          const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
          if (isMounted) {
            const coords = { lat: loc.coords.latitude, lon: loc.coords.longitude };
            setUserLocation(coords);
            cameraRef.current?.easeTo({ center: [coords.lon, coords.lat], zoom: 15, duration: 800 });
          }
        }
      } catch {
        // Silently fall back to field plot
      }
    };
    getLocation();
    return () => { isMounted = false; };
  }, []);

  if (!field) return null;

  const fieldLat = field.latitude;
  const fieldLon = field.longitude;
  const initialZoom = 14;
  const fieldBoundary = useMemo(
    () => (field.area_ha > 0 ? circlePolygon(fieldLat, fieldLon, radiusFromHectares(field.area_ha)) : null),
    [fieldLat, fieldLon, field.area_ha],
  );

  const focusPhone = () => {
    setActiveFocus('phone');
    if (userLocation) {
      cameraRef.current?.easeTo({ center: [userLocation.lon, userLocation.lat], zoom: 15, duration: 600 });
    } else {
      Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High }).then((loc) => {
        const coords = { lat: loc.coords.latitude, lon: loc.coords.longitude };
        setUserLocation(coords);
        cameraRef.current?.easeTo({ center: [coords.lon, coords.lat], zoom: 15, duration: 600 });
      }).catch(() => {});
    }
  };

  const focusField = () => {
    setActiveFocus('field');
    cameraRef.current?.easeTo({ ...fieldCameraStop(fieldLat, fieldLon, initialZoom), duration: 600 });
  };

  return (
    <View style={styles.container}>
      {!online && (
        <View style={styles.offlineBanner}>
          <Banner text={t('cantReachServer')} kind="error" />
        </View>
      )}

      <Map style={styles.container} mapStyle={SATELLITE_STYLE}>
        <Camera
          ref={cameraRef}
          initialViewState={{ center: [fieldLon, fieldLat], zoom: initialZoom }}
        />

        {/* Field acreage boundary: a circle of the farmer's selected area,
            centered on the exact pin -- an approximation (no surveyed
            polygon exists), same "center + radius" assumption any mapping
            tool uses when all it has is a point and an area. */}
        {fieldBoundary && ShapeSource && FillLayer && LineLayer && (
          <ShapeSource id="field-boundary-source" shape={fieldBoundary}>
            <FillLayer id="field-boundary-fill" style={{ fillColor: C.accent, fillOpacity: 0.12 }} />
            <LineLayer id="field-boundary-line" style={{ lineColor: C.accent, lineWidth: 2, lineOpacity: 0.7 }} />
          </ShapeSource>
        )}

        {/* Field location marker -- a classic red map pin, tip anchored to
            the exact lat/lon (Module 60 field finding: the old flat dot
            didn't read as "this exact point" the way a pin's point does). */}
        <Marker
          {...({ anchor: 'bottom', coordinate: [fieldLon, fieldLat] } as any)}
        >
          <View style={styles.markerContainer}>
            <View style={styles.fieldLabel}>
              <Text style={styles.fieldLabelText}>{field.name || 'Field'}</Text>
            </View>
            <RedPin size={40} />
          </View>
        </Marker>

        {/* User live phone location marker */}
        {userLocation && (
          <Marker
            {...({ anchor: 'center', coordinate: [userLocation.lon, userLocation.lat] } as any)}
          >
            <View style={styles.markerContainer}>
              <View style={styles.phoneLabelBubble}>
                <Text style={styles.phoneLabelText}>Your Phone</Text>
              </View>
              <View style={styles.phoneLocationRing}>
                <View style={styles.phoneLocationDot} />
              </View>
            </View>
          </Marker>
        )}
      </Map>

      {/* Top Bar with View Switcher */}
      <View style={styles.topBar}>
        <TouchableOpacity
          onPress={focusPhone}
          activeOpacity={0.85}
          style={{
            backgroundColor: activeFocus === 'phone' ? '#1976D2' : 'rgba(255,255,255,0.92)',
            paddingHorizontal: 12,
            paddingVertical: 8,
            borderRadius: 20,
            borderWidth: 1,
            borderColor: activeFocus === 'phone' ? '#1976D2' : '#D0D8C8',
            shadowColor: '#000',
            shadowOffset: { width: 0, height: 2 },
            shadowOpacity: 0.15,
            shadowRadius: 3,
            elevation: 3,
          }}
        >
          <Text style={{ fontSize: 12, fontWeight: '700', color: activeFocus === 'phone' ? '#fff' : C.text }}>
            📍 Your Phone
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          onPress={focusField}
          activeOpacity={0.85}
          style={{
            backgroundColor: activeFocus === 'field' ? C.accent : 'rgba(255,255,255,0.92)',
            paddingHorizontal: 12,
            paddingVertical: 8,
            borderRadius: 20,
            borderWidth: 1,
            borderColor: activeFocus === 'field' ? C.accent : '#D0D8C8',
            shadowColor: '#000',
            shadowOffset: { width: 0, height: 2 },
            shadowOpacity: 0.15,
            shadowRadius: 3,
            elevation: 3,
          }}
        >
          <Text style={{ fontSize: 12, fontWeight: '700', color: activeFocus === 'field' ? '#fff' : C.text }}>
            🌱 Field Plot
          </Text>
        </TouchableOpacity>
      </View>

      {/* Floating GPS Recenter button */}
      <TouchableOpacity
        onPress={focusPhone}
        activeOpacity={0.85}
        style={styles.gpsButton}
      >
        <Icon name="location" size={24} color="#fff" />
      </TouchableOpacity>

      {/* Close button */}
      <TouchableOpacity
        onPress={onClose}
        style={styles.closeButton}
      >
        <Icon name="chevron-back" size={24} color={C.accent} />
      </TouchableOpacity>

      {/* Attribution */}
      <View style={styles.attributionBox}>
        <Icon name="info" size={13} color={C.muted} />
        <Text style={styles.attributionText}>
          © Esri, Maxar, Earthstar Geographics
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  offlineBanner: {
    paddingHorizontal: S.lg,
    paddingTop: S.md,
    paddingBottom: 0,
  },
  markerContainer: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  fieldLabel: {
    backgroundColor: C.accent,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    marginBottom: 4,
  },
  fieldLabelText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '700',
  },
  phoneLabelBubble: {
    backgroundColor: '#1976D2',
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 9,
    marginBottom: 2,
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 2,
    elevation: 3,
  },
  phoneLabelText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.2,
  },
  phoneLocationRing: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: 'rgba(25, 118, 210, 0.22)',
    borderWidth: 1.5,
    borderColor: 'rgba(25, 118, 210, 0.55)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  phoneLocationDot: {
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: '#1976D2',
    borderWidth: 2.5,
    borderColor: '#fff',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.35,
    shadowRadius: 3,
    elevation: 4,
  },
  topBar: {
    position: 'absolute',
    top: S.lg,
    left: 64,
    right: 64,
    flexDirection: 'row',
    justifyContent: 'center',
    gap: S.xs,
  },
  gpsButton: {
    position: 'absolute',
    bottom: 64,
    right: S.lg,
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: '#1976D2',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.3,
    shadowRadius: 5,
    elevation: 5,
  },
  closeButton: {
    position: 'absolute',
    top: S.lg,
    left: S.lg,
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
  },
  attributionBox: {
    position: 'absolute',
    bottom: S.lg,
    left: S.lg,
    right: S.lg,
    backgroundColor: 'rgba(255, 255, 255, 0.92)',
    padding: S.sm,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.15,
    shadowRadius: 2,
  },
  attributionText: {
    marginLeft: S.xs,
    flex: 1,
    fontSize: 11,
    color: C.muted,
    lineHeight: 15,
  },
});
