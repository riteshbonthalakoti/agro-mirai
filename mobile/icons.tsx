import React from 'react';
import Svg, { Path, Circle, Ellipse, Rect } from 'react-native-svg';

// Shared stroke-based icon set (Module 31 redesign) -- one visual family
// for every icon in the app instead of raw emoji glyphs. Path data for
// leaf/drop/blight/sprout/home/camera/list/play/chevrons/bolt/gallery/
// globe/field/mic is transcribed from the published "Field & Grain,
// Reforged" mockup's inline SVG <defs> (viewBox 0 0 24 24, 1.6px stroke).
// speaker/logout/close/location/settings/pause were not in that mockup's
// icon set and are original additions in the same visual language
// (1.6-1.9px stroke, rounded caps/joins) to cover call sites the mockup
// didn't spec a screen for.
export type IconName =
  | 'leaf' | 'drop' | 'blight' | 'sprout' | 'home' | 'camera' | 'list'
  | 'play' | 'pause' | 'chevron-down' | 'chevron-up' | 'chevron-back'
  | 'chevron-right' | 'bolt' | 'gallery' | 'globe' | 'user' | 'field'
  | 'mic' | 'thermo' | 'speaker' | 'logout' | 'close' | 'location'
  | 'settings';

type IconProps = { name: IconName; size?: number; color?: string };

export function Icon({ name, size = 18, color = '#23281F' }: IconProps) {
  const stroke = { stroke: color, strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, fill: 'none' };
  const strokeChevron = { stroke: color, strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, fill: 'none' };

  switch (name) {
    case 'leaf':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M5 19c9 0 14-5 14-14C10 5 5 10 5 19Z" {...stroke} />
          <Path d="M6 18C11 13 15 9 18.5 5.5" {...stroke} />
        </Svg>
      );
    case 'drop':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M12 3s6.5 7.2 6.5 11.5a6.5 6.5 0 1 1-13 0C5.5 10.2 12 3 12 3Z" {...stroke} />
        </Svg>
      );
    case 'blight':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M5 19c9 0 14-5 14-14C10 5 5 10 5 19Z" {...stroke} />
          <Circle cx={10.5} cy={12} r={1.1} fill={color} />
          <Circle cx={14.5} cy={9} r={1.1} fill={color} />
          <Circle cx={8.5} cy={15.5} r={1.1} fill={color} />
        </Svg>
      );
    case 'sprout':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M12 21v-8" {...stroke} />
          <Path d="M12 13C12 8 8 6 4 6c0 4.5 3.5 7 8 7Z" {...stroke} />
          <Path d="M12 10c0-3.5 2.8-6 6.5-6 0 3.6-2.8 6-6.5 6Z" {...stroke} />
        </Svg>
      );
    case 'home':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M4 11.5 12 4l8 7.5" {...stroke} />
          <Path d="M6 10v9.5h12V10" {...stroke} />
          <Path d="M10 19.5v-6h4v6" {...stroke} />
        </Svg>
      );
    case 'camera':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Rect x={3.5} y={7.5} width={17} height={12.5} rx={2.2} {...stroke} />
          <Path d="M8.5 7.5 10 5h4l1.5 2.5" {...stroke} />
          <Circle cx={12} cy={13.7} r={3.4} stroke={color} strokeWidth={1.6} fill="none" />
        </Svg>
      );
    case 'list':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M9 6.5h11M9 12h11M9 17.5h11" stroke={color} strokeWidth={1.6} strokeLinecap="round" />
          <Circle cx={4.5} cy={6.5} r={1.3} fill={color} />
          <Circle cx={4.5} cy={12} r={1.3} fill={color} />
          <Circle cx={4.5} cy={17.5} r={1.3} fill={color} />
        </Svg>
      );
    case 'play':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M6.5 4.5v15l13-7.5-13-7.5Z" fill={color} />
        </Svg>
      );
    case 'pause':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Rect x={6} y={4.5} width={4} height={15} rx={1} fill={color} />
          <Rect x={14} y={4.5} width={4} height={15} rx={1} fill={color} />
        </Svg>
      );
    case 'chevron-down':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M6 9l6 6 6-6" {...strokeChevron} />
        </Svg>
      );
    case 'chevron-up':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M6 15l6-6 6 6" {...strokeChevron} />
        </Svg>
      );
    case 'chevron-back':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M15 5 8 12l7 7" stroke={color} strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </Svg>
      );
    case 'chevron-right':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M9 5l7 7-7 7" {...strokeChevron} />
        </Svg>
      );
    case 'bolt':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M13 3 5 14h5.5L11 21l8-11h-5.5L13 3Z" fill={color} />
        </Svg>
      );
    case 'gallery':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Rect x={3.5} y={4.5} width={17} height={15} rx={2} {...stroke} />
          <Circle cx={8.3} cy={9.5} r={1.6} fill={color} />
          <Path d="M4 17l5-5 4 4 3-3 4 4" {...stroke} />
        </Svg>
      );
    case 'globe':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle cx={12} cy={12} r={8} stroke={color} strokeWidth={1.6} fill="none" />
          <Ellipse cx={12} cy={12} rx={3.2} ry={8} stroke={color} strokeWidth={1.6} fill="none" />
          <Path d="M4.2 9.5h15.6M4.2 14.5h15.6" stroke={color} strokeWidth={1.6} fill="none" />
        </Svg>
      );
    case 'user':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle cx={12} cy={8.2} r={3.5} stroke={color} strokeWidth={1.6} fill="none" />
          <Path d="M5 20c1-4 4-5.8 7-5.8s6 1.8 7 5.8" {...stroke} />
        </Svg>
      );
    case 'field':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M4 19V9l8-5 8 5v10" {...stroke} />
          <Path d="M4 19h16M9 19v-6h6v6" {...stroke} />
        </Svg>
      );
    case 'mic':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Rect x={9} y={3.5} width={6} height={11} rx={3} stroke={color} strokeWidth={1.6} fill="none" />
          <Path d="M6 12a6 6 0 0 0 12 0M12 18v3" {...stroke} />
        </Svg>
      );
    case 'thermo':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M12 4v10.2a3.5 3.5 0 1 1-3 0V6.5" {...stroke} />
          <Circle cx={10.5} cy={16.5} r={1} fill={color} />
        </Svg>
      );
    case 'speaker':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M4 9.5h4l5-4v13l-5-4H4Z" stroke={color} strokeWidth={1.6} strokeLinejoin="round" fill="none" />
          <Path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" {...stroke} />
        </Svg>
      );
    case 'logout':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M9 4H6.5A2.5 2.5 0 0 0 4 6.5v11A2.5 2.5 0 0 0 6.5 20H9" {...stroke} />
          <Path d="M14 8l5 4-5 4M19 12H10" {...stroke} />
        </Svg>
      );
    case 'close':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M5.5 5.5l13 13M18.5 5.5l-13 13" stroke={color} strokeWidth={1.8} strokeLinecap="round" fill="none" />
        </Svg>
      );
    case 'location':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M12 21s7-6.5 7-12a7 7 0 1 0-14 0c0 5.5 7 12 7 12Z" stroke={color} strokeWidth={1.6} strokeLinejoin="round" fill="none" />
          <Circle cx={12} cy={9} r={2.4} stroke={color} strokeWidth={1.6} fill="none" />
        </Svg>
      );
    case 'settings':
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle cx={12} cy={12} r={3} stroke={color} strokeWidth={1.6} fill="none" />
          <Path
            d="M19.4 13.5c.1-.5.1-1 0-1.5l1.6-1.3-1.5-2.6-1.9.6c-.4-.3-.8-.6-1.3-.8L16 5.9h-3l-.3 1.9c-.5.2-.9.5-1.3.8l-1.9-.6-1.5 2.6L9.6 12c-.1.5-.1 1 0 1.5L8 14.8l1.5 2.6 1.9-.6c.4.3.8.6 1.3.8l.3 2h3l.3-1.9c.5-.2.9-.5 1.3-.8l1.9.6 1.5-2.6-1.6-1.4Z"
            stroke={color}
            strokeWidth={1.4}
            strokeLinejoin="round"
            fill="none"
          />
        </Svg>
      );
    default:
      return null;
  }
}
