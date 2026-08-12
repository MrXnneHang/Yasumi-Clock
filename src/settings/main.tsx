import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './settings.css';
import { SettingsWindow } from './SettingsWindow';

const root = document.getElementById('root');
if (!root) {
  throw new Error('settings root is required');
}

createRoot(root).render(
  <StrictMode>
    <SettingsWindow />
  </StrictMode>,
);
