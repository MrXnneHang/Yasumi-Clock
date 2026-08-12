import { getCurrentWindow } from '@tauri-apps/api/window';

export interface MainWindowControls {
  close(): Promise<void>;
  isMaximized(): Promise<boolean>;
  minimize(): Promise<void>;
  onResized(listener: () => void): Promise<() => void>;
  startDragging(): Promise<void>;
  toggleMaximize(): Promise<void>;
}

export const mainWindowControls: MainWindowControls = {
  close: () => getCurrentWindow().close(),
  isMaximized: () => getCurrentWindow().isMaximized(),
  minimize: () => getCurrentWindow().minimize(),
  onResized: (listener) => getCurrentWindow().onResized(listener),
  startDragging: () => getCurrentWindow().startDragging(),
  toggleMaximize: () => getCurrentWindow().toggleMaximize(),
};
