export const APP_VERSION = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : 'dev'
export const APP_REVISION = typeof __APP_REVISION__ !== 'undefined' ? __APP_REVISION__ : 'dev'
export const APP_LABEL = /^v/i.test(APP_VERSION)
  ? 'V ' + APP_VERSION.slice(1).trim()
  : `V ${APP_VERSION}`
