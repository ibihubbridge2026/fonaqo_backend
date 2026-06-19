/**
 * FONACO SuperAdmin — interactions natives (sidebar, onglets, modales, recherche).
 */
(function () {
  'use strict';

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }
  function qsa(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  /* Sidebar mobile + collapse desktop */
  const sidebar = qs('#admin-sidebar');
  const overlay = qs('#admin-sidebar-overlay');
  const toggleBtns = qsa('[data-sidebar-toggle]');
  const collapseBtn = qs('[data-sidebar-collapse]');

  function closeSidebar() {
    document.body.classList.remove('fq-sidebar-open');
    document.body.classList.remove('overflow-hidden');
  }
  function openSidebar() {
    document.body.classList.add('fq-sidebar-open');
    document.body.classList.add('overflow-hidden');
  }
  function toggleSidebarCollapse() {
    document.body.classList.toggle('fq-sidebar-collapsed');
    localStorage.setItem('fq_sidebar_collapsed', document.body.classList.contains('fq-sidebar-collapsed') ? '1' : '0');
  }

  if (localStorage.getItem('fq_sidebar_collapsed') === '1') {
    document.body.classList.add('fq-sidebar-collapsed');
  }

  toggleBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      if (document.body.classList.contains('fq-sidebar-open')) closeSidebar();
      else openSidebar();
    });
  });
  overlay?.addEventListener('click', closeSidebar);
  collapseBtn?.addEventListener('click', toggleSidebarCollapse);

  /* Sous-menu Utilisateurs */
  qsa('.fq-nav-toggle').forEach((btn) => {
    btn.addEventListener('click', () => {
      const group = btn.closest('.fq-nav-group');
      if (!group) return;
      const isOpen = group.classList.toggle('open');
      btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
  });

  /* Horloge temps réel */
  function updateClock() {
    const now = new Date();
    const dateEl = qs('#fq-clock-date');
    const timeEl = qs('#fq-clock-time');
    if (dateEl) {
      dateEl.textContent = now.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
    }
    if (timeEl) {
      timeEl.textContent = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
  }
  updateClock();
  setInterval(updateClock, 1000);

  /* Onglets internes */
  qsa('[data-tabs]').forEach((tabsRoot) => {
    const buttons = qsa('[data-tab-btn]', tabsRoot);
    const panels = qsa('[data-tab-panel]', tabsRoot);
    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const target = btn.getAttribute('data-tab-btn');
        buttons.forEach((b) => {
          const active = b === btn;
          b.classList.toggle('active', active);
          b.classList.toggle('fq-tab', true);
          b.classList.toggle('fonaco-tab', true);
        });
        panels.forEach((p) => {
          p.classList.toggle('hidden', p.getAttribute('data-tab-panel') !== target);
        });
      });
    });
  });

  /* Tiroir / modale KYC */
  const kycDrawer = qs('#kyc-drawer');
  const kycOverlay = qs('#kyc-drawer-overlay');

  function closeKycDrawer() {
    kycDrawer?.classList.remove('open');
    kycDrawer?.classList.add('translate-x-full');
    kycOverlay?.classList.add('hidden');
  }

  qsa('[data-kyc-open]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-kyc-open');
      const row = qs(`[data-agent-row="${id}"]`);
      if (!row || !kycDrawer) return;
      qs('#kyc-agent-name', kycDrawer).textContent = row.dataset.name || '—';
      qs('#kyc-agent-username', kycDrawer).textContent = row.dataset.username || '—';
      qs('#kyc-id-preview', kycDrawer).src = row.dataset.idCard || '';
      qs('#kyc-selfie-preview', kycDrawer).src = row.dataset.selfie || '';
      qs('#kyc-profile-id', kycDrawer).value = id;
      const kycStatus = row.dataset.kyc || '';
      const actions = qs('#kyc-drawer-actions', kycDrawer);
      if (actions) {
        actions.classList.toggle('hidden', kycStatus === 'APPROVED');
      }
      kycDrawer.classList.remove('translate-x-full');
      kycDrawer.classList.add('open');
      kycOverlay?.classList.remove('hidden');
    });
  });

  qsa('[data-kyc-close]').forEach((el) => el.addEventListener('click', closeKycDrawer));
  kycOverlay?.addEventListener('click', closeKycDrawer);

  qsa('[data-kyc-action]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const action = btn.getAttribute('data-kyc-action');
      const profileId = qs('#kyc-profile-id')?.value;
      if (!profileId) return;
      const url =
        action === 'approve'
          ? `/api/v1/staff/kyc/${profileId}/approve/`
          : `/api/v1/staff/kyc/${profileId}/reject/`;
      btn.disabled = true;
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrf(),
            'Content-Type': 'application/json',
          },
          credentials: 'same-origin',
        });
        if (res.ok) {
          const row = qs(`[data-agent-row="${profileId}"]`);
          if (row) {
            const badge = qs('[data-kyc-badge]', row);
            if (badge) {
              badge.textContent = action === 'approve' ? 'Approuvé' : 'Rejeté';
              badge.className =
                action === 'approve'
                  ? 'px-2 py-1 rounded-full bg-green-50 text-green-700 text-label-sm border border-green-200'
                  : 'px-2 py-1 rounded-full bg-red-50 text-red-700 text-label-sm border border-red-200';
            }
          }
          closeKycDrawer();
        } else {
          showToast('Action KYC impossible — vérifiez votre session admin.', true);
        }
      } catch (e) {
        showToast('Erreur réseau.', true);
      } finally {
        btn.disabled = false;
      }
    });
  });

  /* Détails mission (accordéon) */
  qsa('[data-mission-toggle]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-mission-toggle');
      const panel = qs(`[data-mission-detail="${id}"]`);
      panel?.classList.toggle('hidden');
      btn.querySelector('svg')?.classList.toggle('rotate-180');
    });
  });

  /* Recherche globale */
  const globalSearch = qs('#global-admin-search');
  globalSearch?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const q = globalSearch.value.trim();
      if (!q) return;
      if (q.length >= 4) {
        window.location.href = `/track/?ref=${encodeURIComponent(q)}`;
      } else {
        window.location.href = `/admin-dashboard/missions/?q=${encodeURIComponent(q)}`;
      }
    }
  });

  /* Notifications cloche — panel léger */
  const notifBtn = qs('#admin-notif-btn');
  const notifPanel = qs('#admin-notif-panel');
  notifBtn?.addEventListener('click', async (e) => {
    e.stopPropagation();
    notifPanel?.classList.toggle('hidden');
    if (!notifPanel || notifPanel.dataset.loaded) return;
    try {
      const res = await fetch('/api/v1/core/admin-notifications/?limit=8', {
        credentials: 'same-origin',
      });
      if (!res.ok) return;
      const data = await res.json();
      const list = qs('#admin-notif-list', notifPanel);
      if (!list) return;
      list.innerHTML = '';
      (data.results || []).forEach((n) => {
        const li = document.createElement('li');
        li.className = 'px-4 py-3 border-b border-outline-variant hover:bg-surface-container-low';
        li.innerHTML = `<p class="font-bold text-sm">${n.title}</p><p class="text-xs text-on-surface-variant">${n.message}</p>`;
        list.appendChild(li);
      });
      notifPanel.dataset.loaded = '1';
    } catch (_) {}
  });
  document.addEventListener('click', () => notifPanel?.classList.add('hidden'));

  function getCsrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  /* Suivi public AJAX */
  const trackForm = qs('#public-track-form');
  trackForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = qs('#public-track-ref');
    const ref = input?.value.trim();
    if (!ref) return;
    const result = qs('#public-track-result');
    const loading = qs('#public-track-loading');
    result?.classList.add('hidden');
    loading?.classList.remove('hidden');
    try {
      const res = await fetch(
        `/api/v1/public/mission-track/?reference=${encodeURIComponent(ref)}`,
      );
      const data = await res.json();
      loading?.classList.add('hidden');
      if (!data.found) {
        qs('#public-track-error')?.classList.remove('hidden');
        return;
      }
      qs('#public-track-error')?.classList.add('hidden');
      renderPublicTimeline(data.mission);
      result?.classList.remove('hidden');
    } catch (_) {
      loading?.classList.add('hidden');
      qs('#public-track-error')?.classList.remove('hidden');
    }
  });

  function renderPublicTimeline(m) {
    const title = qs('#public-mission-title');
    const meta = qs('#public-mission-meta');
    const timeline = qs('#public-timeline');
    if (title) title.textContent = m.title;
    if (meta) {
      meta.textContent = `Réf. ${m.short_ref} · ${m.status_label} · ${m.budget_total.toLocaleString('fr-FR')} FCFA`;
    }
    if (!timeline) return;
    timeline.innerHTML = '';
    m.timeline.forEach((step) => {
      const li = document.createElement('li');
      li.className = 'flex gap-4 items-start';
      const dot =
        step.state === 'done'
          ? 'bg-primary ring-4 ring-primary/20'
          : step.state === 'current'
            ? 'bg-secondary ring-4 ring-secondary/20 animate-pulse'
            : 'bg-outline-variant';
      li.innerHTML = `
        <div class="mt-1 w-3 h-3 rounded-full flex-shrink-0 ${dot}"></div>
        <div class="flex-1 pb-6 border-l border-outline-variant pl-6 -ml-[1.35rem]">
          <p class="font-bold ${step.state === 'upcoming' ? 'text-on-surface-variant' : 'text-on-surface'}">${step.label}</p>
          ${step.timestamp ? `<p class="text-xs font-mono-data text-on-surface-variant">${new Date(step.timestamp).toLocaleString('fr-FR')}</p>` : ''}
        </div>`;
      timeline.appendChild(li);
    });
    const alert = qs('#public-pending-alert');
    if (alert) {
      alert.classList.toggle('hidden', !m.pending_unassigned_alert);
    }
  }

  if (typeof window.__FONACO_TRACK_REF === 'string' && window.__FONACO_TRACK_REF) {
    const input = qs('#public-track-ref');
    if (input) {
      input.value = window.__FONACO_TRACK_REF;
      trackForm?.dispatchEvent(new Event('submit'));
    }
  }

  /* Modales génériques */
  qsa('[data-modal-close]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-modal-close');
      qs(`#${id}`)?.classList.add('hidden');
      qs(`#${id}-overlay`)?.classList.add('hidden');
    });
  });

  function openModal(id) {
    qs(`#${id}`)?.classList.remove('hidden');
    qs(`#${id}-overlay`)?.classList.remove('hidden');
  }
  function closeModal(id) {
    qs(`#${id}`)?.classList.add('hidden');
    qs(`#${id}-overlay`)?.classList.add('hidden');
  }

  function showToast(msg, isError) {
    const t = qs('#admin-toast');
    if (!t) return;
    t.textContent = msg;
    t.className = `fq-toast fonaco-toast${isError ? ' error' : ''}`;
    t.classList.remove('hidden');
    setTimeout(() => t.classList.add('hidden'), 3500);
  }

  async function staffFetch(url, options = {}) {
    const res = await fetch(url, {
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken': getCsrf(),
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      ...options,
    });
    let body = null;
    try { body = await res.json(); } catch (_) {}
    return { ok: res.ok, status: res.status, body };
  }

  /** Dé-enveloppe la réponse StandardizedJSONRenderer (+ legacy { data: { data } }). */
  function parseStaffResponse(body) {
    if (!body || typeof body !== 'object') {
      return { data: null, error: 'Réponse vide' };
    }
    if (body.status === 'error') {
      return { data: null, error: body.message || 'Erreur API', errors: body.errors };
    }
    let d = body.data !== undefined ? body.data : body;
    if (
      d && typeof d === 'object' && !Array.isArray(d)
      && d.data !== undefined && typeof d.results === 'undefined'
      && typeof d.volume_escrow === 'undefined' && typeof d.escrow_volume === 'undefined'
    ) {
      d = d.data;
    }
    return { data: d, error: null };
  }

  function staffLogError(context, status, detail) {
    console.error(`[FonacoAdmin] ${context} — HTTP ${status}${detail ? `: ${detail}` : ''}`);
  }

  function missionStatusBadge(status, label) {
    const map = {
      PENDING: 'fq-badge-pending',
      ACCEPTED: 'fq-badge-accepted',
      ON_THE_WAY: 'fq-badge-progress',
      ARRIVED: 'fq-badge-progress',
      IN_PROGRESS: 'fq-badge-progress',
      IN_PROGRESS_REVIEW: 'fq-badge-progress',
      COMPLETED: 'fq-badge-completed',
      CANCELLED: 'fq-badge-cancelled',
      DISPUTED: 'fq-badge-disputed',
    };
    const cls = map[status] || 'fq-badge-default';
    return `<span class="fq-badge ${cls}">${label || status}</span>`;
  }

  /* Actions data-admin-action */
  qsa('[data-admin-action]').forEach((el) => {
    el.addEventListener('click', () => handleAdminAction(el));
  });

  async function handleAdminAction(el) {
    const action = el.getAttribute('data-admin-action');
    if (action === 'open-assign') {
      const mid = el.getAttribute('data-mission-id');
      const ref = el.getAttribute('data-mission-ref');
      qs('#assign-mission-id').value = mid;
      qs('#assign-mission-ref').textContent = ref;
      openModal('modal-assign');
      return;
    }
    if (action === 'open-arbitrage') {
      const did = qs('#active-dispute-id')?.value;
      if (!did) { showToast('Sélectionnez un litige dans le tableau', true); return; }
      qs('#arbitrage-dispute-id').value = did;
      openModal('modal-arbitrage');
      return;
    }
    if (action === 'dispute-resolve') {
      const disputeId = qs('#active-dispute-id')?.value;
      const resolution = el.getAttribute('data-resolution');
      if (!disputeId) { showToast('Sélectionnez un litige', true); return; }
      const { ok } = await staffFetch(`/api/v1/disputes/${disputeId}/resolve/`, {
        method: 'POST',
        body: JSON.stringify({ resolution_type: resolution, notes: '' }),
      });
      showToast(ok ? 'Litige résolu' : 'API litige non disponible — sprint backend', !ok);
      return;
    }
    if (action === 'view-row-detail') {
      const row = el.closest('tr');
      const raw = row?.getAttribute('data-row-detail');
      if (!raw) { showToast('Aucun détail disponible', true); return; }
      try {
        const data = JSON.parse(raw);
        const body = qs('#row-detail-body');
        body.innerHTML = Object.entries(data).map(([k, v]) =>
          `<div class="flex justify-between gap-4 py-2 border-b border-[var(--fq-border-light)]"><span class="text-[var(--fq-muted)]">${k}</span><span class="font-medium text-right break-all">${v ?? '—'}</span></div>`
        ).join('');
        qs('#row-detail-title').textContent = data.Nom || data.Username || data['Code agent'] || 'Détails';
        openModal('modal-row-detail');
      } catch (e) {
        showToast('Erreur affichage détails', true);
      }
      return;
    }
    if (action === 'close-row-detail') {
      closeModal('modal-row-detail');
      return;
    }
    if (action === 'toggle-internal') {
      const pid = el.getAttribute('data-profile-id');
      showConfirm('Basculer le statut Agent Interne ?', async () => {
        const { ok } = await staffFetch(`/api/v1/staff/agents/${pid}/toggle-internal/`, { method: 'POST' });
        showToast(ok ? 'Statut interne mis à jour' : 'Erreur', !ok);
        if (ok) setTimeout(() => location.reload(), 600);
      });
      return;
    }
    if (action === 'approve-badge') {
      const pid = el.getAttribute('data-profile-id');
      showConfirm('Valider la photo badge et notifier l\'agent ?', async () => {
        const { ok } = await staffFetch(`/api/v1/staff/badges/${pid}/approve/`, { method: 'POST' });
        showToast(ok ? 'Badge validé — email envoyé' : 'Erreur validation', !ok);
        if (ok) setTimeout(() => location.reload(), 600);
      });
      return;
    }

    if (action === 'promote-artisan') {
      const uid = el.getAttribute('data-user-id');
      const uname = el.getAttribute('data-username');
      showConfirm(`Promouvoir ${uname} en Artisan Expert ?`, async () => {
        const { ok } = await staffFetch(`/api/v1/staff/users/${uid}/promote-artisan/`, { method: 'POST' });
        showToast(ok ? 'Ajouté à l\'annuaire LeBonCoin' : 'Erreur publication annuaire', !ok);
        if (ok) setTimeout(() => location.reload(), 600);
      });
      return;
    }
    if (action === 'suspend-user') {
      const uid = el.getAttribute('data-user-id');
      showConfirm('Suspendre ce compte ? L\'utilisateur ne pourra plus se connecter.', async () => {
        const { ok } = await staffFetch(`/api/v1/staff/users/${uid}/suspend/`, { method: 'POST' });
        showToast(ok ? 'Compte suspendu' : 'Erreur suspension', !ok);
        if (ok) setTimeout(() => location.reload(), 600);
      });
      return;
    }
    if (action === 'reactivate-user') {
      const uid = el.getAttribute('data-user-id');
      showConfirm('Réactiver ce compte ?', async () => {
        const { ok } = await staffFetch(`/api/v1/staff/users/${uid}/reactivate/`, { method: 'POST' });
        showToast(ok ? 'Compte réactivé' : 'Erreur réactivation', !ok);
        if (ok) setTimeout(() => location.reload(), 600);
      });
      return;
    }
    if (action === 'force-cancel-mission') {
      const mid = el.getAttribute('data-mission-id');
      showConfirm('Annuler définitivement cette mission fantôme ?', async () => {
        const { ok } = await staffFetch(`/api/v1/staff/missions/${mid}/force-cancel/`, { method: 'POST' });
        if (ok) el.closest('[class*="flex"]')?.remove();
        showToast(ok ? 'Mission annulée' : 'API force-cancel à implémenter', !ok);
      });
      return;
    }
    if (action === 'cancel-boost') {
      const bid = el.getAttribute('data-boost-id');
      showConfirm('Annuler ce boost actif ?', async () => {
        const { ok } = await staffFetch(`/api/v1/staff/boosts/${bid}/cancel/`, { method: 'POST' });
        showToast(ok ? 'Boost annulé' : 'API boost cancel — vérifier endpoint', !ok);
      });
      return;
    }
    if (action === 'payout-approve') {
      const pid = el.getAttribute('data-payout-id');
      const { ok } = await staffFetch(`/api/v1/staff/payouts/${pid}/approve/`, { method: 'POST' });
      showToast(ok ? 'Payout approuvé' : 'API approve à implémenter', !ok);
      if (ok) window.FonacoAdmin?.loadPayouts();
      return;
    }
    if (action === 'payout-reject') {
      const pid = el.getAttribute('data-payout-id');
      showConfirm('Rejeter ce retrait ?', async () => {
        const { ok } = await staffFetch(`/api/v1/staff/payouts/${pid}/reject/`, { method: 'POST' });
        showToast(ok ? 'Payout rejeté' : 'API reject à implémenter', !ok);
        if (ok) window.FonacoAdmin?.loadPayouts();
      });
      return;
    }
    if (action === 'create-influencer') {
      qs('#influencer-edit-id').value = '';
      qs('#influencer-modal-title').textContent = 'Nouvel influenceur';
      qs('#form-influencer-modal').reset();
      qs('#influencer-rate').value = '0.02';
      qs('#influencer-duration').value = '2';
      openModal('modal-influencer');
      return;
    }
    if (action === 'edit-influencer') {
      qs('#influencer-edit-id').value = el.getAttribute('data-influencer-id');
      qs('#influencer-modal-title').textContent = 'Modifier influenceur';
      qs('#influencer-name').value = el.getAttribute('data-influencer-name') || '';
      qs('#influencer-code').value = el.getAttribute('data-influencer-code') || '';
      qs('#influencer-slug').value = el.getAttribute('data-influencer-slug') || '';
      qs('#influencer-rate').value = el.getAttribute('data-commission-rate') || '0.02';
      qs('#influencer-duration').value = el.getAttribute('data-duration-years') || '2';
      openModal('modal-influencer');
      return;
    }
    if (action === 'open-artisan-create') {
      qs('#form-artisan-create')?.reset();
      openModal('modal-artisan');
      return;
    }
    if (action === 'revoke-artisan') {
      const uid = el.getAttribute('data-user-id');
      const uname = el.getAttribute('data-username');
      showConfirm(`Rétrograder ${uname} (perte statut artisan) ?`, async () => {
        const { ok } = await staffFetch(`/api/v1/staff/artisans/${uid}/revoke/`, { method: 'POST' });
        showToast(ok ? 'Artisan rétrogradé' : 'Erreur rétrogradation', !ok);
        if (ok) setTimeout(() => location.reload(), 800);
      });
      return;
    }
    if (action === 'open-staff-create') {
      qs('#form-staff-create')?.reset();
      openModal('modal-staff');
      return;
    }
    if (action === 'open-withdrawal-request') {
      qs('#withdrawal-influencer-id').value = el.getAttribute('data-influencer-id');
      qs('#form-withdrawal-request')?.reset();
      openModal('modal-withdrawal-request');
      return;
    }
    if (action === 'open-influencer-portal-link') {
      qs('#portal-link-influencer-id').value = el.getAttribute('data-influencer-id');
      qs('#form-influencer-portal')?.reset();
      openModal('modal-influencer-portal');
      return;
    }
    if (action === 'approve-influencer-withdrawal') {
      const wid = el.getAttribute('data-withdrawal-id');
      const amt = el.getAttribute('data-withdrawal-amount');
      qs('#withdrawal-approve-id').value = wid;
      qs('#withdrawal-approve-amount').textContent = `${Number(amt).toLocaleString('fr-FR')} FCFA`;
      qs('#form-withdrawal-approve')?.reset();
      openModal('modal-withdrawal-approve');
      return;
    }
    if (action === 'reject-influencer-withdrawal') {
      const wid = el.getAttribute('data-withdrawal-id');
      showConfirm('Rejeter cette demande de retrait ?', async () => {
        const { ok } = await staffFetch(`/api/v1/staff/influencer-withdrawals/${wid}/reject/`, {
          method: 'POST',
          body: JSON.stringify({ admin_note: '' }),
        });
        showToast(ok ? 'Demande rejetée' : 'Erreur', !ok);
        if (ok) window.FonacoAdmin?.loadInfluencerDetail();
      });
      return;
    }
    if (action === 'payout-influencer') {
      const iid = el.getAttribute('data-influencer-id');
      showConfirm('Verser le solde commissions disponible ?', async () => {
        const { ok, body } = await staffFetch(`/api/v1/staff/influencers/${iid}/payout/`, {
          method: 'POST',
          body: JSON.stringify({}),
        });
        showToast(ok ? `Versé ${body?.paid_amount} FCFA` : 'Erreur versement', !ok);
      });
      return;
    }
    if (action === 'edit-boost-plan') {
      qs('#boost-plan-id').value = el.getAttribute('data-plan-id');
      qs('#boost-plan-price').value = el.getAttribute('data-plan-price');
      qs('#boost-plan-hours').value = el.getAttribute('data-plan-hours');
      openModal('modal-boost-plan');
      return;
    }
    if (action === 'save-ops-note') {
      const note = qs('#ops-notes')?.value || '';
      localStorage.setItem('fonaco_ops_note', note);
      showToast('Note enregistrée localement (API notes équipe à venir)', false);
      return;
    }
    if (action === 'refresh-payouts') window.FonacoAdmin?.loadPayouts();
    if (action === 'refresh-audit') window.FonacoAdmin?.loadAuditLog();
    if (action === 'refresh-boosts') location.reload();
    if (action === 'refresh-escrow') window.FonacoAdmin?.loadEscrowDisputes();
  }

  let confirmCallback = null;
  function showConfirm(message, onConfirm) {
    qs('#confirm-message').textContent = message;
    confirmCallback = onConfirm;
    openModal('modal-confirm');
  }
  qs('#confirm-action-btn')?.addEventListener('click', async () => {
    closeModal('modal-confirm');
    if (confirmCallback) await confirmCallback();
    confirmCallback = null;
  });

  qs('#form-assign-agent')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const missionId = qs('#assign-mission-id').value;
    const agentId = qs('#assign-agent-id').value;
    const { ok } = await staffFetch(`/api/v1/staff/missions/${missionId}/assign/`, {
      method: 'POST',
      body: JSON.stringify({ agent_id: agentId }),
    });
    closeModal('modal-assign');
    showToast(ok ? 'Agent assigné' : 'API assign à implémenter', !ok);
  });

  qs('#form-arbitrage-split')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const disputeId = qs('#active-dispute-id')?.value || qs('#arbitrage-dispute-id')?.value;
    const clientPct = qs('#arbitrage-client-pct').value;
    const agentPct = qs('#arbitrage-agent-pct').value;
    const notes = qs('#arbitrage-notes').value;
    const { ok } = await staffFetch(`/api/v1/disputes/${disputeId}/resolve/`, {
      method: 'POST',
      body: JSON.stringify({
        resolution_type: 'ARBITRAGE_SPLIT',
        client_percent: clientPct,
        agent_percent: agentPct,
        notes,
      }),
    });
    closeModal('modal-arbitrage');
    showToast(ok ? 'Arbitrage appliqué' : 'API arbitrage à implémenter', !ok);
  });

  qs('#form-influencer-modal')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const editId = qs('#influencer-edit-id')?.value;
    const payload = {
      name: qs('#influencer-name').value.trim(),
      code_promo: qs('#influencer-code').value.trim(),
      referral_slug: qs('#influencer-slug').value.trim() || undefined,
      commission_rate: qs('#influencer-rate').value,
      duration_years: parseInt(qs('#influencer-duration').value, 10) || 2,
    };
    const url = editId ? `/api/v1/staff/influencers/${editId}/` : '/api/v1/staff/influencers/';
    const { ok } = await staffFetch(url, {
      method: editId ? 'PATCH' : 'POST',
      body: JSON.stringify(payload),
    });
    closeModal('modal-influencer');
    showToast(ok ? 'Influenceur enregistré' : 'Erreur enregistrement', !ok);
    if (ok) setTimeout(() => location.reload(), 800);
  });

  qs('#form-artisan-create')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    const { ok } = await staffFetch('/api/v1/staff/artisans/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    closeModal('modal-artisan');
    showToast(ok ? 'Artisan créé' : 'Erreur création artisan', !ok);
    if (ok) setTimeout(() => location.reload(), 800);
  });

  qs('#form-staff-create')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    const { ok } = await staffFetch('/api/v1/staff/staff-users/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    closeModal('modal-staff');
    showToast(ok ? 'Compte staff créé' : 'Erreur création staff', !ok);
    if (ok) setTimeout(() => location.reload(), 800);
  });

  qs('#form-boost-plan')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const pid = qs('#boost-plan-id').value;
    const { ok } = await staffFetch(`/api/v1/staff/boosts/plans/${pid}/`, {
      method: 'PATCH',
      body: JSON.stringify({
        price: qs('#boost-plan-price').value,
        duration_hours: qs('#boost-plan-hours').value,
      }),
    });
    closeModal('modal-boost-plan');
    showToast(ok ? 'Forfait mis à jour' : 'Erreur', !ok);
    if (ok) setTimeout(() => location.reload(), 800);
  });

  ['modal-influencer', 'modal-artisan', 'modal-staff', 'modal-boost-plan', 'modal-assign', 'modal-arbitrage', 'modal-confirm', 'modal-withdrawal-request', 'modal-withdrawal-approve', 'modal-influencer-portal', 'modal-row-detail'].forEach((id) => {
    qs(`#${id}-overlay`)?.addEventListener('click', () => closeModal(id));
  });

  qs('#form-withdrawal-request')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const iid = qs('#withdrawal-influencer-id').value;
    const { ok } = await staffFetch(`/api/v1/staff/influencers/${iid}/withdrawals/`, {
      method: 'POST',
      body: JSON.stringify({
        amount: qs('#withdrawal-amount').value,
        note: qs('#withdrawal-note').value,
      }),
    });
    closeModal('modal-withdrawal-request');
    showToast(ok ? 'Demande envoyée' : 'Erreur envoi', !ok);
    if (ok) window.FonacoAdmin?.loadInfluencerDetail();
  });

  qs('#form-withdrawal-approve')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const wid = qs('#withdrawal-approve-id').value;
    const fd = new FormData();
    const file = qs('#withdrawal-proof-file')?.files?.[0];
    if (!file) { showToast('Preuve requise', true); return; }
    fd.append('proof_file', file);
    fd.append('admin_note', qs('#withdrawal-admin-note')?.value || '');
    const res = await fetch(`/api/v1/staff/influencer-withdrawals/${wid}/approve/`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCsrf() },
      body: fd,
    });
    closeModal('modal-withdrawal-approve');
    showToast(res.ok ? 'Retrait validé' : 'Erreur validation', !res.ok);
    if (res.ok) window.FonacoAdmin?.loadInfluencerDetail();
  });

  qs('#form-influencer-portal')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const iid = qs('#portal-link-influencer-id').value;
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    const { ok } = await staffFetch(`/api/v1/staff/influencers/${iid}/portal-user/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    closeModal('modal-influencer-portal');
    showToast(ok ? 'Accès portail créé' : 'Erreur création', !ok);
    if (ok) setTimeout(() => location.reload(), 800);
  });

  document.querySelectorAll('[data-password-toggle]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = qs(`#${btn.getAttribute('data-password-toggle')}`);
      if (!input) return;
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.querySelector('.fq-eye-open')?.classList.toggle('hidden', !show);
      btn.querySelector('.fq-eye-closed')?.classList.toggle('hidden', show);
    });
  });

  /* API namespace pour pages */
  window.FonacoAdmin = {
    initAssignAgents() {
      const raw = qs('#assign-agents-json');
      if (!raw) return;
      try {
        const agents = JSON.parse(raw.textContent);
        const sel = qs('#assign-agent-id');
        if (!sel) return;
        sel.innerHTML = '<option value="">— Choisir un agent —</option>';
        agents.forEach((a) => {
          const o = document.createElement('option');
          o.value = a.id;
          o.textContent = `@${a.username}`;
          sel.appendChild(o);
        });
      } catch (_) {}
    },
    async loadPlatformFees() {
      try {
        const { ok, body } = await staffFetch('/api/v1/staff/platform-config/');
        const { data } = parseStaffResponse(body);
        if (!ok || !data) return;
        const urgent = data.fees_urgent ?? data.FEES_URGENT;
        const conf = data.fees_confidential ?? data.FEES_CONFIDENTIAL;
        if (urgent != null) qs('#fees-urgent').value = urgent;
        if (conf != null) qs('#fees-confidential').value = conf;
        const split = data.revenue_split || {};
        const agentPct = split.agent_pct ?? data.SPLIT_AGENT_PCT ?? 88;
        const platformPct = split.platform_pct ?? data.SPLIT_PLATFORM_PCT ?? 10;
        const influencerPct = split.influencer_pct ?? data.SPLIT_INFLUENCER_PCT ?? 2;
        if (qs('#split-agent-pct')) qs('#split-agent-pct').value = agentPct;
        if (qs('#split-platform-pct')) qs('#split-platform-pct').value = platformPct;
        if (qs('#split-influencer-pct')) qs('#split-influencer-pct').value = influencerPct;
        if (data.BOOST_PROMO_PERCENT != null && qs('#boost-promo-percent')) {
          qs('#boost-promo-percent').value = data.BOOST_PROMO_PERCENT;
        }
        if (data.BOOST_PROMO_UNTIL && qs('#boost-promo-until')) {
          const d = String(data.BOOST_PROMO_UNTIL).slice(0, 10);
          if (d) qs('#boost-promo-until').value = d;
        }
        const delayMin = data.AGENT_MISSION_DELAY_MINUTES;
        if (delayMin != null && qs('#agent-mission-delay')) {
          qs('#agent-mission-delay').value = delayMin;
          const delayEl = qs('#delay-value');
          if (delayEl) delayEl.textContent = delayMin;
        }
      } catch (_) {}
    },
    async loadConfigKeys() {
      const list = qs('#config-keys-list');
      if (!list) return;
      try {
        const { ok, body } = await staffFetch('/api/v1/staff/platform-config/');
        const { data } = parseStaffResponse(body);
        if (!ok || !data) {
          list.innerHTML = '<p class="text-on-surface-variant text-sm">Configuration indisponible.</p>';
          return;
        }
        const entries = Object.entries(data).filter(([k]) => k === k.toUpperCase() || k.startsWith('fees_'));
        list.innerHTML = entries.map(([k, v]) => `
          <div class="flex justify-between items-center p-3 rounded-xl bg-surface-container-low border border-outline-variant/50 hover:border-fonaco/40 transition-colors">
            <code class="text-xs font-mono-data text-primary font-semibold">${k}</code>
            <span class="font-mono-data text-sm font-bold">${v}</span>
          </div>`).join('');
      } catch (_) {
        list.innerHTML = '<p class="text-error text-sm">Erreur chargement config.</p>';
      }
    },
    bindConfigForm() {
      qs('#form-platform-fees')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
          FEES_URGENT: qs('#fees-urgent').value,
          FEES_CONFIDENTIAL: qs('#fees-confidential').value,
        };
        const { ok } = await staffFetch('/api/v1/staff/platform-config/', {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        showToast(ok ? 'Frais enregistrés' : 'Erreur enregistrement', !ok);
      });
      qs('#form-revenue-split')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const a = Number(qs('#split-agent-pct').value);
        const p = Number(qs('#split-platform-pct').value);
        const i = Number(qs('#split-influencer-pct').value);
        const warn = qs('#split-sum-warning');
        if (a + p + i !== 100) {
          warn?.classList.remove('hidden');
          showToast('La somme des parts doit être 100%', true);
          return;
        }
        warn?.classList.add('hidden');
        showConfirm('Modifier le split escrow ? Action sensible.', async () => {
          const { ok } = await staffFetch('/api/v1/staff/platform-config/', {
            method: 'PATCH',
            body: JSON.stringify({
              SPLIT_AGENT_PCT: a,
              SPLIT_PLATFORM_PCT: p,
              SPLIT_INFLUENCER_PCT: i,
            }),
          });
          showToast(ok ? 'Split escrow mis à jour' : 'Erreur', !ok);
        });
      });
      qs('#form-boost-promo')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const until = qs('#boost-promo-until').value;
        const { ok } = await staffFetch('/api/v1/staff/platform-config/', {
          method: 'PATCH',
          body: JSON.stringify({
            BOOST_PROMO_PERCENT: qs('#boost-promo-percent').value || '0',
            BOOST_PROMO_UNTIL: until ? `${until}T23:59:59` : '',
          }),
        });
        showToast(ok ? 'Promo boost enregistrée' : 'Erreur', !ok);
      });
      qs('#form-agent-delay')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const delay = qs('#agent-mission-delay').value;
        const { ok } = await staffFetch('/api/v1/staff/platform-config/', {
          method: 'PATCH',
          body: JSON.stringify({ AGENT_MISSION_DELAY_MINUTES: delay }),
        });
        if (ok) {
          const delayEl = qs('#delay-value');
          if (delayEl) delayEl.textContent = delay;
        }
        showToast(ok ? 'Délai missions enregistré' : 'Erreur enregistrement', !ok);
      });
    },
    async loadStaffProfile() {
      const form = qs('#form-staff-profile');
      if (!form) return;
      try {
        const { ok, body } = await staffFetch('/api/v1/staff/me/');
        const { data } = parseStaffResponse(body);
        if (!ok || !data) return;
        const set = (id, val) => {
          const el = qs(id);
          if (el) el.value = val ?? '';
        };
        set('#staff-profile-username', data.username);
        set('#staff-profile-role', data.role_label);
        set('#staff-profile-first-name', data.first_name);
        set('#staff-profile-last-name', data.last_name);
        set('#staff-profile-email', data.email);
      } catch (_) {}
    },
    bindStaffSecurityForms() {
      qs('#form-staff-profile')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
          first_name: qs('#staff-profile-first-name')?.value?.trim(),
          last_name: qs('#staff-profile-last-name')?.value?.trim(),
          email: qs('#staff-profile-email')?.value?.trim(),
        };
        const { ok } = await staffFetch('/api/v1/staff/me/', {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        showToast(ok ? 'Profil mis à jour' : 'Erreur mise à jour profil', !ok);
        if (ok) this.loadStaffProfile();
      });
      qs('#form-staff-password')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const newPwd = qs('#staff-password-new')?.value || '';
        const confirmPwd = qs('#staff-password-confirm')?.value || '';
        if (newPwd !== confirmPwd) {
          showToast('Les mots de passe ne correspondent pas', true);
          return;
        }
        const { ok } = await staffFetch('/api/v1/staff/me/password/', {
          method: 'POST',
          body: JSON.stringify({
            old_password: qs('#staff-password-old')?.value,
            new_password: newPwd,
            confirm_password: confirmPwd,
          }),
        });
        showToast(ok ? 'Mot de passe changé' : 'Erreur — vérifiez l\'ancien mot de passe', !ok);
        if (ok) e.target.reset();
      });
    },
    async loadPasswordResets() {
      const body = qs('#password-resets-body');
      if (!body) return;
      try {
        const { ok, body } = await staffFetch('/api/v1/staff/password-resets/');
        const { data } = parseStaffResponse(body);
        const rows = data?.results || body?.results || [];
        if (!ok) {
          body.innerHTML = '<tr><td colspan="4" class="text-center py-8 text-red-600">Erreur chargement</td></tr>';
          return;
        }
        body.innerHTML = rows.length ? rows.map((r) => `
          <tr>
            <td class="mono text-xs">${r.requested_at}</td>
            <td class="mono font-semibold">${r.phone_number}</td>
            <td>${r.full_name || r.username}</td>
            <td class="text-right">
              <button type="button" class="fq-btn fq-btn-primary fq-btn-sm" data-reset-id="${r.id}">Réinitialiser</button>
            </td>
          </tr>`).join('') : '<tr><td colspan="4" class="text-center py-8 text-[var(--fq-muted)]">Aucune demande en attente.</td></tr>';
        qsa('[data-reset-id]', body).forEach((btn) => {
          btn.addEventListener('click', async () => {
            const id = btn.getAttribute('data-reset-id');
            const { ok, body: resBody } = await staffFetch(`/api/v1/staff/password-resets/${id}/process/`, { method: 'POST' });
            const { data: res } = parseStaffResponse(resBody);
            if (!ok) {
              showToast('Erreur réinitialisation', true);
              return;
            }
            const msg = res?.sms_message || res?.temp_password || '';
            await navigator.clipboard?.writeText(msg);
            showToast('Mot de passe généré — message copié dans le presse-papiers', false);
            window.FonacoAdmin?.loadPasswordResets();
          });
        });
      } catch (_) {
        body.innerHTML = '<tr><td colspan="4" class="text-center py-8 text-red-600">Erreur réseau</td></tr>';
      }
    },
    async loadInfluencerDetail() {
      const root = qs('#influencer-detail-root');
      if (!root) return;
      const id = root.dataset.influencerId;
      const canAdmin = root.dataset.canAdmin === '1';
      const fmt = (n) => `${Number(n).toLocaleString('fr-FR')} FCFA`;
      try {
        const { ok, body } = await staffFetch(`/api/v1/staff/influencers/${id}/detail/`);
        const { data } = parseStaffResponse(body);
        if (!ok || !data) return;
        qsa('[data-inf]', root).forEach((el) => {
          const k = el.getAttribute('data-inf');
          if (k === 'commission_rate') {
            el.textContent = `${(Number(data.commission_rate) * 100).toFixed(1)}%`;
          } else if (k === 'duration_years') {
            el.textContent = `${data.duration_years} an(s)`;
          } else if (['balance_current', 'total_earned', 'total_withdrawn'].includes(k)) {
            el.textContent = fmt(data[k]);
          } else if (k === 'clients_count') {
            el.textContent = String(data.clients_count);
          } else {
            el.textContent = data[k] || '—';
          }
        });
        const clientsBody = qs('#influencer-clients-body');
        if (clientsBody) {
          const rows = data.clients || [];
          clientsBody.innerHTML = rows.length ? rows.map((c) => `
            <tr>
              <td class="font-semibold">${c.name}</td>
              <td class="mono">${c.phone}</td>
              <td class="mono text-xs">${c.linked_at}</td>
              <td class="mono">${c.missions_count}</td>
              <td class="text-right mono">${fmt(c.missions_amount)}</td>
              <td class="text-right mono font-semibold">${fmt(c.influencer_benefit)}</td>
            </tr>`).join('') : '<tr><td colspan="6" class="text-center py-8 text-[var(--fq-muted)]">Aucun client parrainé.</td></tr>';
        }
        const wBody = qs('#influencer-withdrawals-body');
        if (wBody) {
          const wrows = data.withdrawals || [];
          wBody.innerHTML = wrows.length ? wrows.map((w) => `
            <tr>
              <td class="mono text-xs">${w.requested_at}</td>
              <td class="mono font-semibold">${fmt(w.amount)}</td>
              <td><span class="fq-badge fq-badge-${w.status === 'APPROVED' ? 'completed' : w.status === 'REJECTED' ? 'cancelled' : 'pending'}">${w.status}</span></td>
              <td class="text-sm text-[var(--fq-muted)]">${w.note || '—'}${w.proof_url ? ` · <a href="${w.proof_url}" target="_blank" class="text-[var(--fq-black)] underline">Preuve</a>` : ''}</td>
              ${canAdmin && w.status === 'PENDING' ? `<td class="text-right space-x-1">
                <button type="button" data-admin-action="approve-influencer-withdrawal" data-withdrawal-id="${w.id}" data-withdrawal-amount="${w.amount}" class="fq-btn fq-btn-primary fq-btn-sm">Valider</button>
                <button type="button" data-admin-action="reject-influencer-withdrawal" data-withdrawal-id="${w.id}" class="fq-btn fq-btn-ghost fq-btn-sm">Rejeter</button>
              </td>` : canAdmin ? '<td></td>' : ''}
            </tr>`).join('') : `<tr><td colspan="${canAdmin ? 5 : 4}" class="text-center py-8 text-[var(--fq-muted)]">Aucune demande.</td></tr>`;
          qsa('[data-admin-action]', wBody).forEach((el) => el.addEventListener('click', () => handleAdminAction(el)));
        }
      } catch (err) {
        console.error('[FonacoAdmin] loadInfluencerDetail', err);
      }
    },
    bindTableFilters() {
      const bindSearch = (inputId, rowSelector) => {
        const input = qs(`#${inputId}`);
        if (!input) return;
        input.addEventListener('input', () => {
          const q = input.value.toLowerCase();
          qsa(rowSelector).forEach((row) => {
            const hay = (row.dataset.search || row.textContent || '').toLowerCase();
            row.classList.toggle('hidden', q && !hay.includes(q));
          });
        });
      };
      bindSearch('agents-filter', '.agent-row');
      bindSearch('clients-filter', '.client-row');
      bindSearch('artisans-filter', '.artisan-row');

      qsa('[data-filter-kyc]').forEach((chip) => {
        chip.addEventListener('click', () => {
          const filter = chip.getAttribute('data-filter-kyc');
          qsa('[data-filter-kyc]').forEach((c) => c.classList.toggle('active', c === chip));
          qsa('.agent-row').forEach((row) => {
            const kyc = row.dataset.kyc || '';
            row.classList.toggle('hidden', filter && kyc !== filter);
          });
        });
      });
    },
    async loadWallet() {
      const fmt = (n) => (n != null ? `${Number(n).toLocaleString('fr-FR')} FCFA` : '—');
      try {
        const { ok, body } = await staffFetch('/api/v1/staff/wallet/summary/');
        const { data } = parseStaffResponse(body);
        if (!ok || !data) return;
        qsa('[data-wallet]').forEach((el) => {
          const key = el.getAttribute('data-wallet');
          if (data[key] != null) el.textContent = fmt(data[key]);
        });
        const tbody = qs('#wallet-history-body');
        if (!tbody) return;
        const rows = data.history || [];
        if (!rows.length) {
          tbody.innerHTML = '<tr><td colspan="4" class="text-center py-8 text-[var(--fq-muted)]">Aucune entrée.</td></tr>';
          return;
        }
        tbody.innerHTML = rows.map((h) => `
          <tr>
            <td class="mono text-xs">${h.created_at}</td>
            <td><span class="fq-badge fq-badge-default">${h.type}</span></td>
            <td class="mono font-semibold">${Number(h.amount).toLocaleString('fr-FR')} FCFA</td>
            <td class="text-sm text-[var(--fq-muted)]">${h.description || '—'}</td>
          </tr>`).join('');
      } catch (err) {
        console.error('[FonacoAdmin] loadWallet', err);
      }
    },
    async loadDashboard() {
      await Promise.all([
        this.loadDashboardKpis(),
        this.loadDashboardActivity(),
        this.loadRecentMissions(),
      ]);
    },
    async loadDashboardKpis() {
      const fmt = (n) => (n != null ? `${Number(n).toLocaleString('fr-FR')} FCFA` : '—');
      const set = (key, val) => {
        const el = qs(`[data-kpi="${key}"]`);
        if (el) {
          el.textContent = val;
          el.classList.remove('is-loading');
        }
      };
      const setBar = (name, pct) => {
        const bar = qs(`[data-bar="${name}"]`);
        if (bar) bar.style.width = `${Math.min(100, Math.max(0, pct))}%`;
      };
      try {
        const { ok, status, body } = await staffFetch('/api/v1/staff/dashboard/kpis/');
        const { data, error } = parseStaffResponse(body);
        if (!ok || !data) {
          staffLogError('GET /staff/dashboard/kpis/', status, error || (status === 403 ? 'Accès staff requis' : 'Données indisponibles'));
          ['volume_escrow', 'active_missions', 'agents_count', 'platform_revenue', 'payouts_pending', 'disputes_open'].forEach((k) => set(k, '—'));
          return;
        }
        set('volume_escrow', fmt(data.volume_escrow ?? data.escrow_volume));
        set('active_missions', String(data.active_missions ?? '—'));
        set('agents_count', String(data.agents_count ?? '—'));
        set('platform_revenue', fmt(data.platform_revenue));
        if (data.payouts_pending != null) set('payouts_pending', String(data.payouts_pending));
        if (data.disputes_open != null) set('disputes_open', String(data.disputes_open));
        const split = data.revenue_split || {};
        const agentPct = split.agent_pct ?? data.split_agent ?? 88;
        const platformPct = split.platform_pct ?? data.split_platform ?? 10;
        const influencerPct = split.influencer_pct ?? data.split_influencer ?? 2;
        set('split_agent', `${agentPct}%`);
        set('split_platform', `${platformPct}%`);
        set('split_influencer', `${influencerPct}%`);
        setBar('agent', agentPct);
        setBar('platform', platformPct);
        setBar('influencer', influencerPct);
      } catch (err) {
        console.error('[FonacoAdmin] loadDashboardKpis exception', err);
      }
    },
    renderActivityRows(rows, container) {
      if (!container) return;
      const severityDot = {
        critical: 'critical',
        warning: 'warning',
        info: 'info',
      };
      if (!rows.length) {
        container.innerHTML = '<p class="text-sm text-[var(--fq-muted)] italic py-4">Aucune activité récente.</p>';
        return;
      }
      container.innerHTML = rows.map((item) => `
        <div class="fq-timeline-item">
          <span class="fq-timeline-dot ${severityDot[item.severity] || 'info'}"></span>
          <div class="min-w-0 flex-1">
            <p class="font-semibold text-sm text-[var(--fq-text)]">${item.time} · ${item.label}</p>
            <p class="text-xs text-[var(--fq-muted)] truncate mt-0.5">${item.detail || ''}</p>
          </div>
        </div>`).join('');
    },
    async loadDashboardActivity() {
      const container = qs('#dashboard-activity');
      if (!container) return;
      try {
        const { ok, status, body } = await staffFetch('/api/v1/staff/dashboard/activity/?limit=10');
        const { data, error } = parseStaffResponse(body);
        const rows = data?.results || [];
        if (!ok) {
          staffLogError('GET /staff/dashboard/activity/', status, error);
          container.innerHTML = '<p class="text-xs text-error">Impossible de charger l\'activité live.</p>';
          return;
        }
        this.renderActivityRows(rows, container);
      } catch (err) {
        console.error('[FonacoAdmin] loadDashboardActivity exception', err);
        container.innerHTML = '<p class="text-xs text-error">Erreur réseau — activité live.</p>';
      }
    },
    async loadOpsActivity() {
      const container = qs('#ops-activity-feed');
      if (!container) return;
      try {
        const { ok, body } = await staffFetch('/api/v1/staff/dashboard/activity/?limit=8');
        const { data } = parseStaffResponse(body);
        if (!ok) {
          container.innerHTML = '<p class="text-xs text-on-surface-variant">Activité indisponible.</p>';
          return;
        }
        this.renderActivityRows(data?.results || [], container);
      } catch (_) {
        container.innerHTML = '<p class="text-xs text-error">Erreur réseau.</p>';
      }
    },
    async loadRecentMissions() {
      const tbody = qs('#dashboard-recent-missions');
      if (!tbody) return;
      try {
        const { ok, status, body } = await staffFetch('/api/v1/staff/dashboard/recent-missions/?limit=8');
        const { data, error } = parseStaffResponse(body);
        const rows = data?.results || [];
        if (!ok || !rows.length) {
          if (!ok) staffLogError('GET /staff/dashboard/recent-missions/', status, error);
          tbody.innerHTML = `<tr><td colspan="4" class="px-6 py-6 text-center text-on-surface-variant text-sm">${ok ? 'Aucune mission en base.' : 'Impossible de charger les missions.'}</td></tr>`;
          return;
        }
        tbody.innerHTML = rows.map((m) => `
          <tr>
            <td class="mono font-semibold text-[var(--fq-black)]">${m.ref}</td>
            <td>${m.client}</td>
            <td>${m.agent || '<span class="text-[var(--fq-muted)]">—</span>'}</td>
            <td class="mono font-semibold">${Number(m.amount).toLocaleString('fr-FR')} FCFA</td>
            <td>${missionStatusBadge(m.status, m.status_label)}</td>
            <td class="mono text-xs text-[var(--fq-muted)]">${m.created_at || '—'}</td>
          </tr>`).join('');
      } catch (err) {
        console.error('[FonacoAdmin] loadRecentMissions exception', err);
        tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-6 text-center text-error text-sm">Erreur réseau — missions.</td></tr>';
      }
    },
    async loadPayouts() {
      const tbody = qs('#payouts-tbody');
      if (!tbody) return;
      const { ok, body } = await staffFetch('/api/v1/staff/payouts/pending/');
      if (!ok || !body) {
        tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-6 text-center text-on-surface-variant text-sm">Aucun retrait en attente.</td></tr>`;
        const kpi = qs('[data-kpi="payouts_pending"]');
        if (kpi) kpi.textContent = '0';
        return;
      }
      const parsed = parseStaffResponse(body);
      const rows = parsed.data?.results || parsed.data || [];
      tbody.innerHTML = rows.map((p) => `
        <tr>
          <td class="mono text-xs">${p.id}</td>
          <td class="font-semibold">${p.agent_name || p.username}</td>
          <td class="text-right mono font-bold">${Number(p.amount).toLocaleString('fr-FR')} FCFA</td>
          <td><span class="fq-badge fq-badge-pending">${p.status || 'PENDING'}</span></td>
          <td class="text-right">
            <button type="button" data-admin-action="payout-approve" data-payout-id="${p.id}" class="fq-btn fq-btn-primary fq-btn-sm" style="min-height:32px;padding:0 10px">✓</button>
            <button type="button" data-admin-action="payout-reject" data-payout-id="${p.id}" class="fq-btn fq-btn-danger fq-btn-sm ml-1" style="min-height:32px;padding:0 10px">✕</button>
          </td>
        </tr>`).join('');
      qsa('[data-admin-action]', tbody).forEach((el) => el.addEventListener('click', () => handleAdminAction(el)));
      const kpi = qs('[data-kpi="payouts_pending"]');
      if (kpi) kpi.textContent = String(rows.length);
    },
    async loadEscrowDisputes() {
      const tbody = qs('#escrow-tbody');
      if (!tbody) return;
      const { ok, body } = await staffFetch('/api/v1/staff/escrow/disputed/');
      if (!ok) {
        tbody.innerHTML = `<tr><td colspan="5" class="p-8 text-center text-sm text-on-surface-variant">Aucun litige ouvert.</td></tr>`;
        const kpi = qs('[data-kpi="disputes_open"]');
        if (kpi) kpi.textContent = '0';
        return;
      }
      const parsed = parseStaffResponse(body);
      const rows = parsed.data?.results || [];
      tbody.innerHTML = rows.map((r) => `
        <tr class="hover:bg-surface-container-low cursor-pointer border-l-4 ${r.status === 'DISPUTED' ? 'border-secondary bg-secondary-container/5' : 'border-transparent'}"
          data-dispute-row="${r.dispute_id}" data-dispute-id="${r.dispute_id}">
          <td class="p-4 font-mono-data">#${r.mission_ref}</td>
          <td class="p-4">${r.client}</td>
          <td class="p-4">${r.agent || '—'}</td>
          <td class="p-4 font-semibold">${r.amount} FCFA</td>
          <td class="p-4"><span class="px-2 py-1 rounded-full text-xs font-bold">${r.escrow_status}</span></td>
        </tr>`).join('');
      qsa('[data-dispute-row]', tbody).forEach((row) => {
        row.addEventListener('click', () => {
          qs('#active-dispute-id').value = row.dataset.disputeId;
          qs('#arbitrage-dispute-id').value = row.dataset.disputeId;
          qs('#dispute-panel-subtitle').textContent = `Litige #${row.dataset.disputeId}`;
        });
      });
      const kpi = qs('[data-kpi="disputes_open"]');
      if (kpi) kpi.textContent = String(rows.length);
    },
    async loadAuditLog() {
      const tbody = qs('#audit-log-body');
      if (!tbody) return;
      const { ok, body } = await staffFetch('/api/v1/staff/audit-log/');
      if (!ok) {
        tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-12 text-center text-on-surface-variant">Aucune entrée d'audit pour le moment.</td></tr>`;
        return;
      }
      const parsed = parseStaffResponse(body);
      const rows = parsed.data?.results || [];
      qs('#audit-count').textContent = `${rows.length} entrées`;
      tbody.innerHTML = rows.map((e) => `
        <tr class="hover:bg-fonaco/5 text-sm audit-row" data-action="${(e.action || '').toUpperCase()}">
          <td class="px-4 py-3 font-mono-data text-xs">${e.created_at}</td>
          <td class="px-4 py-3">${e.admin_username}</td>
          <td class="px-4 py-3"><span class="px-2 py-0.5 bg-fonaco/20 text-fonaco-black text-xs font-bold rounded">${e.action}</span></td>
          <td class="px-4 py-3 font-mono-data text-xs">${e.target}</td>
          <td class="px-4 py-3 text-on-surface-variant">${e.detail || ''}</td>
        </tr>`).join('');
      this._auditRows = rows;
      this.filterAuditLog();
    },
    _auditRows: [],
    filterAuditLog() {
      const q = (qs('#audit-search')?.value || '').toLowerCase();
      const cat = qs('#audit-filter')?.value || '';
      qsa('.audit-row').forEach((row) => {
        const text = row.textContent.toLowerCase();
        const action = row.dataset.action || '';
        const matchQ = !q || text.includes(q);
        const matchCat = !cat || action.includes(cat);
        row.classList.toggle('hidden', !(matchQ && matchCat));
      });
    },
    bindMissionsFilter() {
      const input = qs('#missions-filter');
      if (!input) return;
      input.addEventListener('input', () => {
        const q = input.value.toLowerCase();
        qsa('.mission-row').forEach((row) => {
          const hay = (row.dataset.search || '').toLowerCase();
          row.classList.toggle('hidden', q && !hay.includes(q));
          const detail = qs(`[data-mission-detail="${row.querySelector('[data-mission-toggle]')?.getAttribute('data-mission-toggle')}"]`);
          if (row.classList.contains('hidden') && detail) detail.classList.add('hidden');
        });
      });
    },
    bindOpsNotes() {
      const note = qs('#ops-notes');
      if (!note) return;
      const saved = localStorage.getItem('fonaco_ops_note');
      if (saved) note.value = saved;
    },
    bindInfluencerForm() {
      qs('#form-influencer-quick')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const payload = {
          name: fd.get('name'),
          code_promo: fd.get('code_promo'),
          referral_slug: fd.get('referral_slug') || fd.get('code_promo'),
          commission_rate: fd.get('commission_rate'),
        };
        const { ok } = await staffFetch('/api/v1/staff/influencers/', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        showToast(ok ? 'Influenceur créé' : 'Erreur création', !ok);
        if (ok) setTimeout(() => location.reload(), 600);
      });
    },
    bindAuditFilters() {
      qs('#audit-search')?.addEventListener('input', () => this.filterAuditLog());
      qs('#audit-filter')?.addEventListener('change', () => this.filterAuditLog());
    },
    bindRadiusSlider() {
      qs('#radius-slider')?.addEventListener('input', function () {
        const el = qs('#radius-value');
        if (el) el.textContent = this.value;
      });
    },
    _dashboardTimer: null,
    startDashboardAutoRefresh() {
      if (this._dashboardTimer) clearInterval(this._dashboardTimer);
      if (!qs('#dashboard-kpis')) return;
      this._dashboardTimer = setInterval(() => this.loadDashboard(), 30000);
    },
    initPage() {
      const page = document.body.dataset.adminPage || '';
      this.bindRadiusSlider();
      this.bindMissionsFilter();
      this.bindTableFilters();
      this.bindOpsNotes();
      this.bindInfluencerForm();
      this.bindAuditFilters();

      qs('#dashboard-refresh-btn')?.addEventListener('click', () => {
        this.loadDashboard();
        showToast('Tableau de bord actualisé', false);
      });
      qs('#wallet-refresh-btn')?.addEventListener('click', () => {
        this.loadWallet();
        showToast('Wallet actualisé', false);
      });

      if (page === 'dashboard' || qs('#dashboard-kpis')) {
        this.loadDashboard();
        this.startDashboardAutoRefresh();
        const rangeEl = qs('#fq-date-range-label');
        if (rangeEl) {
          const end = new Date();
          const start = new Date();
          start.setDate(start.getDate() - 6);
          rangeEl.textContent = `${start.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })} – ${end.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })}`;
        }
      }
      if (page === 'operations') {
        this.initAssignAgents();
        this.loadOpsActivity();
      }
      if (page === 'transactions' || qs('#escrow-tbody')) {
        this.loadEscrowDisputes();
        this.loadPayouts();
      }
      if (page === 'wallet' || qs('#wallet-kpis')) {
        this.loadWallet();
      }
      if (page === 'audit' || qs('#audit-log-body')) {
        this.loadAuditLog();
      }
      if (page === 'config' || qs('#form-platform-fees')) {
        this.loadPlatformFees();
        this.loadConfigKeys();
        this.bindConfigForm();
      }
      if (page === 'profile' || qs('#form-staff-profile')) {
        this.loadStaffProfile();
        this.bindStaffSecurityForms();
      }
      if (qs('#influencer-detail-root')) {
        this.loadInfluencerDetail();
      }
      if (page === 'missions' || qs('#assign-agents-json')) {
        this.initAssignAgents();
      }
      if (page === 'password_resets' || qs('#password-resets-body')) {
        this.loadPasswordResets();
      }

      const urlTab = new URLSearchParams(window.location.search).get('tab');
      if (urlTab) {
        const tabBtn = qs(`[data-tab-btn="${urlTab}"]`);
        if (tabBtn) tabBtn.click();
      }
    },
  };

  document.addEventListener('DOMContentLoaded', () => {
    if (window.FonacoAdmin) window.FonacoAdmin.initPage();
  });
})();
