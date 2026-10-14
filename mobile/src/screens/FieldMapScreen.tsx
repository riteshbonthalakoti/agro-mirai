import React, { useEffect, useRef, useState } from 'react';
import { TouchableOpacity, View, Text } from 'react-native';
let Map: any = View;
let Camera: any = View;
let Marker: any = View;
let hasMapLibre = false;

try {
  const ML = require('@maplibre/maplibre-react-native');
  if (ML && (ML.Map || ML.MapView)) {
    Map = ML.Map || ML.MapView;
    Camera = ML.Camera;
    Marker = ML.Marker;
    hasMapLibre = true;
  }
} catch {
  hasMapLibre = false;
}
type CameraRef = any;
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
    <View style={{ flex: 1 }}>
      {!online && (
        <View style={{ paddingHorizontal: S.lg, paddingTop: S.md, paddingBottom: 0 }}>
          <Banner text={t('cantReachServer')} kind="error" />
        </View>
      )}

      <Map style={{ flex: 1 }} mapStyle={SATELLITE_STYLE}>
        <Camera
          ref={cameraRef}
          initialViewState={{ center: [fieldLon, fieldLat], zoom: initialZoom }}
        />

        {/* Field location marker */}
        <Marker
          {...({ anchor: 'bottom', coordinate: [fieldLon, fieldLat] } as any)}
        >
          <View style={{ alignItems: 'center', justifyContent: 'center' }}>
            <View style={{ backgroundColor: C.accent, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10, marginBottom: 4 }}>
              <Text style={{ color: '#fff', fontSize: 10, fontWeight: '700' }}>{field.name || 'Field'}</Text>
            </View>
            <View
              style={{
                width: 32,
                height: 32,
                borderRadius: 16,
                backgroundColor: C.accent,
                alignItems: 'center',
                justifyContent: 'center',
                borderWidth: 2,
                borderColor: '#fff',
                shadowColor: '#000',
                shadowOffset: { width: 0, height: 2 },
                shadowOpacity: 0.35,
                shadowRadius: 4,
              }}
            >
              <Icon name="location" size={18} color="#fff" />
            </View>
          </View>
        </Marker>

        {/* User live phone location marker */}
        {userLocation && (
          <Marker
            {...({ anchor: 'center', coordinate: [userLocation.lon, userLocation.lat] } as any)}
          >
            <View style={{ alignItems: 'center', justifyContent: 'center' }}>
              <View style={{ backgroundColor: '#1976D2', paddingHorizontal: 7, paddingVertical: 2, borderRadius: 9, marginBottom: 2, shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 2, elevation: 3 }}>
                <Text style={{ color: '#fff', fontSize: 10, fontWeight: '800', letterSpacing: 0.2 }}>Your Phone</Text>
              </View>
              <View
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 17,
                  backgroundColor: 'rgba(25, 118, 210, 0.22)',
                  borderWidth: 1.5,
                  borderColor: 'rgba(25, 118, 210, 0.55)',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <View
                  style={{
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
                  }}
                />
              </View>
            </View>
          </Marker>
        )}
      </Map>

      {/* Top Bar with View Switcher */}
      <View
        style={{
          position: 'absolute',
          top: S.lg,
          left: 64,
          right: 64,
          flexDirection: 'row',
          justifyContent: 'center',
          gap: S.xs,
        }}
      >
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
        style={{
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
        }}
      >
        <Icon name="location" size={24} color="#fff" />
      </TouchableOpacity>

      {/* Close button */}
      <TouchableOpacity
        onPress={onClose}
        style={{
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
        }}
      >
        <Icon name="chevron-back" size={24} color={C.accent} />
      </TouchableOpacity>

      {/* Attribution */}
      <View
        style={{
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
        }}
      >
        <Icon name="info" size={13} color={C.muted} />
        <Text style={{ marginLeft: S.xs, flex: 1, fontSize: 11, color: C.muted, lineHeight: 15 }}>
          © Esri, Maxar, Earthstar Geographics
        </Text>
      </View>
    </View>
  );
}
