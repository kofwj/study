export const APP_VERSION = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : 'dev'
export const APP_REVISION = typeof __APP_REVISION__ !== 'undefined' ? __APP_REVISION__ : 'dev'
export const APP_LABEL = APP_REVISION && APP_REVISION !== 'dev'
  ? `${APP_VERSION} · ${APP_REVISION}`
  : APP_VERSION
