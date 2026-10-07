import React, { useEffect, useRef, useState } from 'react';
import { TouchableOpacity, View, Text } from 'react-native';
import { Map, Camera, Marker } from '@maplibre/maplibre-react-native';
import type { CameraRef } from '@maplibre/maplibre-react-native';
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
  const online = isOnline();
  const cameraRef = useRef<CameraRef>(null);

  // Get current location on mount
  useEffect(() => {
    const getLocation = async () => {
      try {
        const perm = await Location.requestForegroundPermissionsAsync();
        if (perm.status === 'granted') {
          const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
          setUserLocation({ lat: loc.coords.latitude, lon: loc.coords.longitude });
        }
      } catch {
        // Silently fail — map still works without user location
      }
    };
    getLocation();
  }, []);

  if (!field) return null;

  const fieldLat = field.latitude;
  const fieldLon = field.longitude;
  const initialZoom = 14;

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
          <View style={{ width: 40, height: 40, alignItems: 'center', justifyContent: 'center' }}>
            <View
              style={{
                width: 32,
                height: 32,
                borderRadius: 16,
                backgroundColor: C.accent,
                alignItems: 'center',
                justifyContent: 'center',
                shadowColor: '#000',
                shadowOffset: { width: 0, height: 2 },
                shadowOpacity: 0.3,
                shadowRadius: 4,
              }}
            >
              <Icon name="location" size={18} color="#fff" />
            </View>
          </View>
        </Marker>

        {/* User location marker */}
        {userLocation && (
          <Marker
            {...({ anchor: 'center', coordinate: [userLocation.lon, userLocation.lat] } as any)}
          >
            <View
              style={{
                width: 16,
                height: 16,
                borderRadius: 8,
                backgroundColor: '#1976D2',
                borderWidth: 3,
                borderColor: '#fff',
                shadowColor: '#000',
                shadowOffset: { width: 0, height: 1 },
                shadowOpacity: 0.3,
                shadowRadius: 2,
              }}
            />
          </Marker>
        )}
      </Map>

      {/* Focus button */}
      <TouchableOpacity
        onPress={() => {
          cameraRef.current?.easeTo(
            { ...fieldCameraStop(fieldLat, fieldLon, initialZoom), duration: 400 }
          );
        }}
        style={{
          position: 'absolute',
          top: S.lg,
          right: S.lg,
          width: 48,
          height: 48,
          borderRadius: 24,
          backgroundColor: C.accent,
          alignItems: 'center',
          justifyContent: 'center',
          shadowColor: '#000',
          shadowOffset: { width: 0, height: 2 },
          shadowOpacity: 0.25,
          shadowRadius: 4,
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
