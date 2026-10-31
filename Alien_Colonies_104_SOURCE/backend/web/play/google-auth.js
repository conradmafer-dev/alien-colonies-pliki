import {t} from './i18n.js?v=0111';

const wait = seconds => new Promise(resolve => setTimeout(resolve,seconds * 1000));

// The browser receives a short-lived flow handle. The game session is claimed
// separately over POST, so neither session tokens nor poll secrets enter URLs.
export async function completeGoogleFlow(api, flow, name) {
  return api('/auth/google/complete',{method:'POST',authenticated:false,body:{flow_id:flow.flow_id,poll_secret:flow.poll_secret,...(name === undefined ? {} : {name})}});
}

export async function beginGoogleFlow(api, {mode = 'login', password = '', onStatus = () => {}, isCurrent = () => true, openWindow = (...args) => window.open(...args), delay = wait, origin = globalThis.location?.origin} = {}) {
  const popup = openWindow('about:blank','alien-colonies-google','popup,width=520,height=680');
  if (!popup) throw new Error(t('Zezwól na wyskakujące okno, aby zalogować się przez Google.'));
  try {
    const ensureCurrent = () => {if (!isCurrent()) throw Object.assign(new Error(t('Logowanie przez Google zostało anulowane.')), {cancelled:true});};
    popup.opener = null;
    onStatus(t('Otwieranie logowania przez Google…'));
    const flow = await api('/auth/google/start',{method:'POST',authenticated:mode === 'link',body:{mode,client:'web',...(mode === 'link' ? {password} : {})}});
    ensureCurrent();
    const authorization = new URL(flow.authorization_url,origin);
    if (authorization.origin !== origin || authorization.pathname !== '/api/auth/google/open' || !flow.flow_id || !flow.poll_secret) throw new Error(t('Nie udało się rozpocząć logowania przez Google.'));
    popup.location.replace(authorization.href);
    onStatus(t('Dokończ logowanie w oknie Google.'));
    const deadline = Date.now() + Math.min(600,Number(flow.expires_in) || 600) * 1000;
    let closedPolls = 0;
    while (Date.now() < deadline) {
      await delay(Math.max(2,Math.min(5,Number(flow.poll_after) || 3)));
      ensureCurrent();
      const result = await api('/auth/google/status',{method:'POST',authenticated:false,body:{flow_id:flow.flow_id,poll_secret:flow.poll_secret}});
      ensureCurrent();
      if (result.status === 'ready') return {result:await completeGoogleFlow(api,flow),mode};
      if (result.status === 'needs_name') return {flow,needsName:true,mode,expiresAt:deadline};
      if (result.status === 'error') throw new Error(result.error || t('Logowanie przez Google nie powiodło się. Spróbuj ponownie.'));
      if (result.status !== 'pending') throw new Error(t('Nie udało się rozpocząć logowania przez Google.'));
      // Allow a callback that closes its window to finish before the next poll.
      closedPolls = popup.closed ? closedPolls + 1 : 0;
      if (closedPolls >= 2) throw new Error(t('Logowanie przez Google zostało anulowane.'));
    }
    throw new Error(t('Logowanie przez Google wygasło. Spróbuj ponownie.'));
  } finally { popup.close(); }
}
