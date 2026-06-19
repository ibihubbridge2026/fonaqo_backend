/**
 * FONACO — Parcours invité vitrine (création + suivi + paiement Escrow)
 */
(function () {
  const cfg = window.__FONACO_GUEST || {};
  const API = cfg.apiBase || '/api/v1/public';

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function getCsrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  async function apiFetch(path, options = {}) {
    const res = await fetch(`${API}${path}`, {
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrf(),
        ...(options.headers || {}),
      },
      ...options,
    });
    let body = null;
    try {
      body = await res.json();
    } catch (_) {}
    const data = body && body.data !== undefined ? body.data : body;
    return { ok: res.ok, status: res.status, data };
  }

  /* ---------- Google Places autocomplete (adresse) ---------- */
  function initPlacesAutocomplete() {
    const input = qs('#guest-address');
    const latInput = qs('#guest-latitude');
    const lngInput = qs('#guest-longitude');
    if (!input || !cfg.googlePlacesApiKey) return;

    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${cfg.googlePlacesApiKey}&libraries=places`;
    script.async = true;
    script.onload = () => {
      const ac = new google.maps.places.Autocomplete(input, {
        fields: ['formatted_address', 'geometry'],
        componentRestrictions: { country: ['bj', 'tg', 'ci', 'sn'] },
      });
      ac.addListener('place_changed', () => {
        const place = ac.getPlace();
        if (!place.geometry) return;
        input.value = place.formatted_address || input.value;
        latInput.value = place.geometry.location.lat();
        lngInput.value = place.geometry.location.lng();
      });
    };
    document.head.appendChild(script);
  }

  /* ---------- Création mission ---------- */
  function initCreateForm() {
    const form = qs('#guest-mission-form');
    if (!form) return;

    initPlacesAutocomplete();

    const desc = qs('#guest-description');
    desc?.addEventListener('input', () => {
      const len = (desc.value || '').length;
      const hint = qs('#guest-labor-hint');
      if (hint) {
        const base = 3500 + Math.floor(len / 20) * 100;
        hint.textContent = `Estimation indicative : ~${Math.min(150000, Math.max(3500, base)).toLocaleString('fr-FR')} FCFA (hors frais plateforme)`;
      }
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const errEl = qs('#guest-form-error');
      const btn = qs('#guest-submit-btn');
      errEl?.classList.add('hidden');
      btn.disabled = true;
      btn.textContent = 'Traitement…';

      const payload = {
        email: qs('#guest-email')?.value.trim(),
        phone: qs('#guest-phone')?.value.trim(),
        description: qs('#guest-description')?.value.trim(),
        address: qs('#guest-address')?.value.trim(),
        latitude: qs('#guest-latitude')?.value || null,
        longitude: qs('#guest-longitude')?.value || null,
        payment_method: qs('#guest-payment-method')?.value || 'MTN',
      };

      const { ok, data } = await apiFetch('/missions/guest-create/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      if (!ok) {
        errEl.textContent = data?.message || 'Erreur lors de la création.';
        errEl.classList.remove('hidden');
        btn.disabled = false;
        btn.innerHTML = '<span class="material-symbols-outlined">shield</span> Créer ma mission & payer en Escrow';
        return;
      }

      await handlePaymentFlow(data);
      showSuccessModal(data);
      btn.disabled = false;
      btn.innerHTML = '<span class="material-symbols-outlined">shield</span> Créer ma mission & payer en Escrow';
    });
  }

  async function handlePaymentFlow(data) {
    if (data.checkout_url) {
      window.location.href = data.checkout_url;
      return;
    }
    if (data.sandbox !== false) {
      await apiFetch('/payments/guest-confirm/', {
        method: 'POST',
        body: JSON.stringify({
          payment_id: data.payment_id,
          tracking_code: data.tracking_code,
          external_reference: data.external_reference,
        }),
      });
      return;
    }
    await apiFetch('/payments/guest-confirm/', {
      method: 'POST',
      body: JSON.stringify({
        payment_id: data.payment_id,
        tracking_code: data.tracking_code,
      }),
    });
  }

  function showSuccessModal(data) {
    const code = data.tracking_code || '';
    qs('#guest-success-code').textContent = code;
    const link = qs('#guest-track-link');
    if (link) link.href = data.track_url || `/vitrine/suivi/?ref=${encodeURIComponent(code)}`;
    qs('#guest-success-overlay')?.classList.remove('hidden');
    qs('#guest-success-modal')?.classList.remove('hidden');

    qs('#guest-copy-code')?.addEventListener('click', () => {
      navigator.clipboard?.writeText(code).then(() => {
        qs('#guest-copy-code').textContent = 'Copié !';
        setTimeout(() => { qs('#guest-copy-code').textContent = 'Copier le code'; }, 2000);
      });
    }, { once: true });
  }

  /* ---------- Suivi mission + polling ---------- */
  let pollTimer = null;
  let currentRef = '';

  function initTrackPage() {
    const form = qs('#guest-track-form');
    if (!form) return;

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const ref = qs('#guest-track-ref')?.value.trim();
      if (!ref) return;
      currentRef = ref;
      loadTrack(ref);
      startPolling();
    });

    if (cfg.initialRef) {
      currentRef = cfg.initialRef;
      loadTrack(cfg.initialRef);
      startPolling();
    }
  }

  function startPolling() {
    stopPolling();
    const ms = cfg.pollIntervalMs || 15000;
    pollTimer = setInterval(() => {
      if (currentRef) loadTrack(currentRef, true);
    }, ms);
  }

  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  async function loadTrack(ref, silent) {
    if (!silent) {
      qs('#guest-track-loading')?.classList.remove('hidden');
      qs('#guest-track-error')?.classList.add('hidden');
      qs('#guest-track-result')?.classList.add('hidden');
    }

    const { ok, data } = await apiFetch(
      `/mission-track/?reference=${encodeURIComponent(ref)}`,
      { method: 'GET' },
    );

    if (!silent) qs('#guest-track-loading')?.classList.add('hidden');

    if (!ok || !data?.found) {
      if (!silent) {
        const err = qs('#guest-track-error');
        err.textContent = data?.message || 'Aucune mission trouvée.';
        err.classList.remove('hidden');
      }
      return;
    }

    renderTrack(data.mission);
    qs('#guest-track-result')?.classList.remove('hidden');
  }

  function renderTrack(m) {
    const code = m.tracking_code || m.short_ref;
    qs('#guest-mission-code').textContent = code;
    qs('#guest-mission-title').textContent = m.title;
    qs('#guest-mission-meta').textContent = `${m.status_label} · ${Number(m.budget_total).toLocaleString('fr-FR')} FCFA`;
    qs('#guest-mission-address')?.querySelector('span:last-child') &&
      (qs('#guest-mission-address').querySelector('span:last-child').textContent = m.address || '—');

    const badge = qs('#guest-mission-status-badge');
    if (badge) {
      badge.textContent = m.status_label;
      badge.className = 'px-3 py-1 rounded-full text-xs font-bold ' + (
        m.status === 'COMPLETED' ? 'bg-green-100 text-green-800' :
        m.status === 'PENDING' ? 'bg-yellow-100 text-yellow-800' :
        'bg-blue-100 text-blue-800'
      );
    }

    qs('#guest-pending-alert')?.classList.toggle('hidden', !m.pending_unassigned_alert);

    const timeline = qs('#guest-timeline');
    if (timeline) {
      timeline.innerHTML = '';
      (m.timeline || []).forEach((step) => {
        const li = document.createElement('li');
        li.className = 'flex gap-4 items-start pb-6';
        const dot = step.state === 'done' ? 'bg-[#00288e] ring-4 ring-blue-100' :
          step.state === 'current' ? 'bg-[#fd761a] ring-4 ring-orange-100 animate-pulse' :
          'bg-gray-300';
        li.innerHTML = `
          <div class="mt-1 w-3 h-3 rounded-full flex-shrink-0 ${dot}"></div>
          <div class="flex-1 border-l border-gray-200 pl-4 -ml-[1.35rem]">
            <p class="font-semibold ${step.state === 'upcoming' ? 'text-gray-400' : ''}">${step.label}</p>
            ${step.timestamp ? `<p class="text-xs text-gray-400 font-mono mt-0.5">${new Date(step.timestamp).toLocaleString('fr-FR')}</p>` : ''}
          </div>`;
        timeline.appendChild(li);
      });
    }

    const agentCard = qs('#guest-agent-card');
    if (m.agent && m.agent.phone) {
      agentCard?.classList.remove('hidden');
      qs('#guest-agent-name').textContent = m.agent.first_name;
      qs('#guest-agent-skills').textContent = m.agent.skills;
      const call = qs('#guest-agent-call');
      if (call) call.href = `tel:${m.agent.phone}`;
    } else {
      agentCard?.classList.add('hidden');
    }

    const proofCard = qs('#guest-proof-card');
    if (m.proof_photo_url && (m.status === 'IN_PROGRESS_REVIEW' || m.status === 'COMPLETED')) {
      proofCard?.classList.remove('hidden');
      const img = qs('#guest-proof-image');
      if (img) img.src = m.proof_photo_url;
    } else {
      proofCard?.classList.add('hidden');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    initCreateForm();
    initTrackPage();
  });

  window.addEventListener('beforeunload', stopPolling);
})();
