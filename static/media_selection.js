/* Player selection never exposes signed media URLs or reads remote previews. */
const mediaSelectionModal = $('#media-selection-modal');
let selectedMediaJob = null;
let mediaSelectionBusy = false;

function closeMediaSelection() {
  if (mediaSelectionBusy) return;
  mediaSelectionModal.classList.add('hidden');
  selectedMediaJob = null;
}
function openMediaSelection(job) {
  selectedMediaJob = job;
  uiText($('#media-selection-message'), '');
  renderMediaSelection();
  mediaSelectionModal.classList.remove('hidden');
  $('#media-selection-close').focus();
}
function reconcileMediaSelection(jobs) {
  if (!selectedMediaJob) return;
  const current = jobs.find((job) => job.id === selectedMediaJob.id);
  if (current && current.status !== 'selecting') {
    selectedMediaJob = null;
    if (!mediaSelectionBusy) closeMediaSelection();
  }
}
function renderMediaSelection() {
  const list = $('#media-selection-list');
  const focused = list.contains(document.activeElement) ? document.activeElement.dataset.selectionId : null;
  list.replaceChildren();
  for (const [index, option] of (selectedMediaJob?.selection_options || []).entries()) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'media-choice'; button.disabled = mediaSelectionBusy;
    button.dataset.selectionId = option.id;
    const title = document.createElement('strong');
    title.textContent = t('ui.player_count', { count: index + 1 }) + (option.title ? ` · ${option.title}` : '');
    const detail = document.createElement('span');
    detail.textContent = [option.host, t('ui.count_source_variants_found', { count: option.variants })].filter(Boolean).join(' · ');
    button.append(title, detail);
    button.addEventListener('click', async () => {
      if (mediaSelectionBusy || !selectedMediaJob) return;
      const job = selectedMediaJob;
      mediaSelectionBusy = true;
      renderMediaSelection();
      uiText($('#media-selection-message'), 'ui.adding');
      try {
        const result = await api('/api/jobs/' + encodeURIComponent(job.id) + '/select-media', {
          method: 'POST', body: JSON.stringify({ selection_id: option.id }),
        });
        render(result);
        mediaSelectionBusy = false;
        closeMediaSelection();
        toast('ui.media_selected_and_queued');
      } catch (error) {
        // Uncertain writes are reconciled by api(); never automatically re-submit.
        uiText($('#media-selection-message'), error.message);
        const current = state.jobs.find((item) => item.id === job.id);
        if (current && current.status !== 'selecting') selectedMediaJob = null;
      } finally {
        mediaSelectionBusy = false;
        if (!selectedMediaJob) closeMediaSelection();
        else renderMediaSelection();
      }
    });
    list.append(button);
    if (focused === option.id && !button.disabled) button.focus({ preventScroll: true });
  }
  if (focused && mediaSelectionBusy) $('#media-selection-close').focus();
}
function renderPlatformCooldown(pacing = {}) {
  const values = Object.entries(pacing.platform_cooldowns || {}).filter(([, item]) => item.cooldown_seconds > 0);
  const summary = $('#platform-cooldown-summary');
  summary.textContent = values.length ? values.map(([platform, item]) =>
    t('ui.platform_cooling_down_for_seconds_s', { platform, seconds: item.cooldown_seconds })).join(' · ') :
    t(pacing.cooldown_seconds > 0 ? 'ui.shared_cooldown_seconds_s' : 'ui.no_platform_cooldowns', { seconds: pacing.cooldown_seconds || 0 });
}
$('#media-selection-close').addEventListener('click', closeMediaSelection);
$('#media-selection-cancel').addEventListener('click', closeMediaSelection);
mediaSelectionModal.addEventListener('click', (event) => { if (event.target === mediaSelectionModal) closeMediaSelection(); });
document.addEventListener('ssdl-language-changed', () => {
  if (selectedMediaJob) renderMediaSelection();
  renderPlatformCooldown(lastResponse?.safe_queue);
});
