const SERVICE_WORKER_URL = '/sw.js';

export const registerServiceWorker = async (): Promise<void> => {
  if (!('serviceWorker' in navigator) || import.meta.env.DEV) {
    return;
  }

  try {
    await navigator.serviceWorker.register(SERVICE_WORKER_URL);
  } catch (error) {
    console.error('Service worker registration failed:', error);
  }
};
