import React from 'react';
import {
  Leaf,
  Droplet,
  Droplets,
  Sprout,
  Home,
  Camera,
  List,
  Play,
  Pause,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Plus,
  Zap,
  Images,
  Globe,
  User,
  Trees,
  Mic,
  Thermometer,
  Volume2,
  LogOut,
  X,
  AlertTriangle,
  Info,
  Bug,
  Image as ImageIcon,
  MapPin,
  Settings,
  Check,
  Bell,
  Wind,
} from 'lucide-react-native';

export type IconName =
  | 'leaf' | 'drop' | 'blight' | 'sprout' | 'home' | 'camera' | 'list'
  | 'play' | 'pause' | 'chevron-down' | 'chevron-up' | 'chevron-back'
  | 'chevron-right' | 'bolt' | 'gallery' | 'globe' | 'user' | 'field'
  | 'mic' | 'thermo' | 'speaker' | 'logout' | 'close' | 'location'
  | 'settings' | 'bell' | 'check' | 'alert' | 'info' | 'bug' | 'image' | 'plus'
  | 'wind' | 'humidity';

type IconProps = { name: IconName; size?: number; color?: string };

export function Icon({ name, size = 18, color = '#23281F' }: IconProps) {
  const strokeWidth = 2.0;

  switch (name) {
    case 'leaf':
      return <Leaf size={size} color={color} strokeWidth={strokeWidth} />;
    case 'drop':
      return <Droplet size={size} color={color} strokeWidth={strokeWidth} />;
    case 'humidity':
      return <Droplets size={size} color={color} strokeWidth={strokeWidth} />;
    case 'wind':
      return <Wind size={size} color={color} strokeWidth={strokeWidth} />;
    case 'blight':
    case 'bug':
      return <Bug size={size} color={color} strokeWidth={strokeWidth} />;
    case 'sprout':
      return <Sprout size={size} color={color} strokeWidth={strokeWidth} />;
    case 'home':
      return <Home size={size} color={color} strokeWidth={strokeWidth} />;
    case 'camera':
      return <Camera size={size} color={color} strokeWidth={strokeWidth} />;
    case 'list':
      return <List size={size} color={color} strokeWidth={strokeWidth} />;
    case 'play':
      return <Play size={size} color={color} strokeWidth={strokeWidth} fill={color} />;
    case 'pause':
      return <Pause size={size} color={color} strokeWidth={strokeWidth} fill={color} />;
    case 'chevron-down':
      return <ChevronDown size={size} color={color} strokeWidth={strokeWidth} />;
    case 'chevron-up':
      return <ChevronUp size={size} color={color} strokeWidth={strokeWidth} />;
    case 'chevron-back':
      return <ChevronLeft size={size} color={color} strokeWidth={strokeWidth} />;
    case 'chevron-right':
      return <ChevronRight size={size} color={color} strokeWidth={strokeWidth} />;
    case 'plus':
      return <Plus size={size} color={color} strokeWidth={strokeWidth} />;
    case 'bolt':
      return <Zap size={size} color={color} strokeWidth={strokeWidth} fill={color} />;
    case 'gallery':
      return <Images size={size} color={color} strokeWidth={strokeWidth} />;
    case 'globe':
      return <Globe size={size} color={color} strokeWidth={strokeWidth} />;
    case 'bell':
      return <Bell size={size} color={color} strokeWidth={strokeWidth} />;
    case 'user':
      return <User size={size} color={color} strokeWidth={strokeWidth} />;
    case 'field':
      return <Trees size={size} color={color} strokeWidth={strokeWidth} />;
    case 'mic':
      return <Mic size={size} color={color} strokeWidth={strokeWidth} />;
    case 'thermo':
      return <Thermometer size={size} color={color} strokeWidth={strokeWidth} />;
    case 'speaker':
      return <Volume2 size={size} color={color} strokeWidth={strokeWidth} />;
    case 'logout':
      return <LogOut size={size} color={color} strokeWidth={strokeWidth} />;
    case 'close':
      return <X size={size} color={color} strokeWidth={strokeWidth} />;
    case 'alert':
      return <AlertTriangle size={size} color={color} strokeWidth={strokeWidth} />;
    case 'info':
      return <Info size={size} color={color} strokeWidth={strokeWidth} />;
    case 'image':
      return <ImageIcon size={size} color={color} strokeWidth={strokeWidth} />;
    case 'location':
      return <MapPin size={size} color={color} strokeWidth={strokeWidth} />;
    case 'settings':
      return <Settings size={size} color={color} strokeWidth={strokeWidth} />;
    case 'check':
      return <Check size={size} color={color} strokeWidth={strokeWidth} />;
    default:
      return null;
  }
}
