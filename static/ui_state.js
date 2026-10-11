/* Shared in-page state. Loaded once before the UI feature scripts. */
const state = { jobs: [], paused: false, ready: false, filter: 'all', platform: 'all', search: '', page: 1, pageSize: 20, xAuth: {}, cookieFile: '', inputMode: 'urls', videoQuality: 'best' };
const jobPageSizes = [10, 20, 50];
const jobPageSizeKey = 'ssdl.jobs.pageSize';
try {
  const savedPageSize = Number(localStorage.getItem(jobPageSizeKey));
  if (jobPageSizes.includes(savedPageSize)) state.pageSize = savedPageSize;
} catch { /* Keep the default when browser storage is unavailable. */ }
const $ = (selector) => document.querySelector(selector);
const rows = $('#job-rows');
const { t, message: uiMessage, text: uiText } = window.I18n;
let lastResponse = null;
let connectionOffline = false;
let resettingRate = false;
let refreshingState = false;
let viewRefreshPending = false;
let resetJobsScroll = false;
let searchTimer = null;
const pendingJobActions = new Map();
let refreshTimer = null;
let lastSuccessfulUpdate = 0;
let lastStatusError = null;
let lastEnvironment = null;
let environmentRenderKey = '';
let environmentRequestBusy = false;
let settingsOpening = false;
let connectingXRequest = false;
const busyControls = new Set();
// Show skip results observed on this page; persisted history reads as Completed.
const recentSkippedJobs = new Map();
