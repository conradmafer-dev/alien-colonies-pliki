import {t} from './i18n.js?v=0111';

const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const bounded = (value, fallback, min, max) => Number.isFinite(Number(value)) ? Math.max(min, Math.min(max, Number(value))) : fallback;

/** One original-tab email sign-in. The HttpOnly browser cookie is supplied by
 * api's same-origin credentials. Polling proofs never enter URLs or storage.
 * Opening the email in another tab only confirms it; this controller alone
 * claims the game session. All asynchronous responses belong to one generation.
 */
export function createEmailFlow(api, {onChange = () => {}, onAuthenticated = () => {}, onDiscardedSession = () => {}, now = () => Date.now(), delay = pause} = {}) {
  let enabled = false, generation = 0, phase = 'closed', email = '', error = '';
  let flow = null, deadline = 0, resendAt = 0, expectedPlayer = '', nameVerified = false;
  const snapshot = () => ({enabled, phase, email, error, nameVerified, resendSeconds:Math.max(0, Math.ceil((resendAt-now())/1000)), canResend:phase === 'waiting' && now() >= resendAt});
  const changed = () => onChange(snapshot());
  const current = id => id === generation && enabled && phase !== 'closed';
  const proof = value => ({flow_id:value.flow_id, poll_secret:value.poll_secret});
  const reset = () => {flow = null; deadline = 0; resendAt = 0; nameVerified = false;};
  const failed = (failure, next = 'email') => {error = failure?.message || t('Nie udało się zalogować przez e-mail. Spróbuj ponownie.');phase = next;changed();};
  const checkExpiry = () => {
    if (flow && ['waiting','name'].includes(phase) && now() >= deadline) {
      generation++;reset();failed(new Error(t('Link logowania wygasł. Wyślij nowy link.')));return true;
    }
    return false;
  };

  async function claim(id, name) {
    if (checkExpiry()) return;
    if (!current(id) || !flow || (phase !== 'waiting' && phase !== 'name')) return;
    const wasName = phase === 'name', claimedFlow = flow;
    phase = 'completing'; error = ''; changed();
    try {
      const result = await api('/auth/email/complete', {method:'POST', authenticated:false, body:{...proof(claimedFlow), ...(name === undefined ? {} : {name})}});
      if (!current(id)) {
        if (result?.token) onDiscardedSession(result.token);
        return;
      }
      if (typeof result?.token !== 'string' || !result.token || !result.state?.player?.id) {if (typeof result?.token === 'string' && result.token) onDiscardedSession(result.token);throw new Error(t('Nie otrzymano sesji gry. Zaloguj się ponownie.'));}
      if (expectedPlayer && result.state.player.id !== expectedPlayer) {
        onDiscardedSession(result.token);reset();failed(new Error(t('Wpisz adres e-mail przypisany do tego imperium.')));return;
      }
      generation++; reset(); phase = 'closed'; email = ''; error = ''; changed();
      onAuthenticated(result);
    } catch (failure) {
      if (!current(id)) return;
      // A taken name can be corrected without sending another email. Invalid
      // cookie/expired-flow failures require a fresh browser-bound challenge.
      if ([401,403,404,410].includes(failure.status)) {reset();failed(failure);}
      else failed(failure, wasName ? 'name' : 'waiting');
    }
  }

  async function poll(id, polledFlow) {
    const interval = bounded(polledFlow.poll_after, 3, 2, 10) * 1000;
    while (current(id) && flow === polledFlow && phase === 'waiting') {
      await delay(interval);
      if (!current(id) || flow !== polledFlow || phase !== 'waiting') return;
      if (now() >= deadline) {reset();failed(new Error(t('Link logowania wygasł. Wyślij nowy link.')));return;}
      try {
        const result = await api('/auth/email/status', {method:'POST', authenticated:false, body:proof(polledFlow)});
        if (!current(id) || flow !== polledFlow || phase !== 'waiting') return;
        if (result.status === 'ready') {await claim(id);if (current(id) && phase === 'waiting' && flow === polledFlow) continue;return;}
        if (result.status === 'needs_name') {if (expectedPlayer) {reset();failed(new Error(t('Wpisz adres e-mail przypisany do tego imperium.')));return;}nameVerified = true;phase = 'name';error = '';changed();return;}
        if (result.status !== 'pending') {
          reset();failed(new Error(result.error || t('Link logowania wygasł. Wyślij nowy link.')));return;
        }
        error = '';changed();
      } catch (failure) {
        if (!current(id) || flow !== polledFlow || phase !== 'waiting') return;
        if ([400,401,403,404,410].includes(failure.status)) {reset();failed(failure);return;}
        // A temporary transport failure does not discard a verified link. The
        // deadline still bounds retries; Cancel and Resend remain available.
        error = failure.message || t('Sprawdź połączenie. Ponawiamy sprawdzanie linku.');changed();
      }
    }
  }

  async function send(value) {
    if (!enabled || !['email','waiting'].includes(phase)) return;
    if (phase === 'waiting' && now() < resendAt) return;
    const candidate = String(value ?? '').trim();
    if (!candidate || candidate.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(candidate)) {failed(new Error(t('Wpisz poprawny adres e-mail.')),phase);return;}
    const id = ++generation;
    reset();email = candidate;phase = 'sending';error = '';changed();
    try {
      const response = await api('/auth/email/start', {method:'POST', authenticated:false, body:{email,client:'web'}});
      if (!current(id)) return;
      if (typeof response.flow_id !== 'string' || !response.flow_id || typeof response.poll_secret !== 'string' || !response.poll_secret) throw new Error(t('Nie udało się rozpocząć logowania przez e-mail.'));
      flow = response;
      deadline = now() + bounded(response.expires_in,900,1,900) * 1000;
      resendAt = now() + bounded(response.resend_after,60,0,900) * 1000;
      phase = 'waiting';error = '';changed();
      void poll(id,flow);
    } catch (failure) {if (current(id)) {reset();failed(failure);}}
  }

  return {
    snapshot,
    checkExpiry,
    configure(value) {enabled = value === true;if (!enabled) {generation++;reset();phase = 'closed';email = '';error = '';}changed();},
    open({expectedPlayerId = ''} = {}) {if (!enabled || phase !== 'closed') return;generation++;reset();expectedPlayer = String(expectedPlayerId);phase = 'email';email = '';error = '';changed();},
    cancel() {generation++;reset();phase = 'closed';email = '';error = '';changed();},
    send,
    resend() {return send(email);},
    submitName(name) {if (phase !== 'name') return Promise.resolve();const value=String(name ?? '').trim();if (value.length < 3 || value.length > 20) {failed(new Error(t('Nazwa imperium musi mieć od 3 do 20 znaków.')),'name');return Promise.resolve();}return claim(generation,value);},
    // Existing-account completion can be retried after a transport failure;
    // nothing is claimed while the mail challenge is still pending.
    checkAgain() {if (phase === 'waiting' && flow) {const id=++generation;void poll(id,flow);}},
  };
}
