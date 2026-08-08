import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './rest-overlay.css';
import { RestOverlay } from './RestOverlay';

const root = document.getElementById('root');
if (!root) {
  throw new Error('rest overlay root is required');
}

createRoot(root).render(
  <StrictMode>
    <RestOverlay />
  </StrictMode>,
);
