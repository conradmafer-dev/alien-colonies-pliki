"""Three real days of beginner protection with persistent, one-time notices.

Notice markers survive report retention, reconnects and restarts. An older empire
whose protection already ended before this feature is not sent historical mail.
All mutations run inside the owning World's transaction.
"""
from __future__ import annotations

try:
    from .i18n import render_text, store_text, t
except ImportError:
    from i18n import render_text, store_text, t


PROTECTION_SECONDS = 3 * 86400
LEGACY_PROTECTION_SECONDS = 86400
PROTECTION_DURATION_VERSION = 2

START_TEXT = (
    'Twoje imperium jest objęte ochroną początkującego. Przez 3 dni od założenia '
    'imperium wszystkie twoje kolonie są chronione przed atakiem i przejęciem. '
    'Atak lub próba przejęcia kolonii innego gracza oraz wysłanie wsparcia '
    'sojuszu kończą ochronę wcześniej. O jej zakończeniu otrzymasz raport.'
)
LEGACY_START_TEXT = START_TEXT.replace('Przez 3 dni', 'Przez dobę', 1)
END_TEXT = 'Twoje kolonie mogą teraz zostać zaatakowane. Zadbaj o flotę i obronę swoich planet.'


class BeginnerProtectionMixin:
    def _upgrade_beginner_protection(self, player):
        """Extend a live old deadline once, before replaying offline events.

        Startup calls this with the actual current time, not the saved event
        cursor. Expired or deliberately ended protection is never restored.
        New accounts already carry this policy version and need no extension.
        """
        version = player.get('protection_duration_version', 1)
        if type(version) is int and version >= PROTECTION_DURATION_VERSION:
            return False
        notice = player.get('protection_notice')
        ended = isinstance(notice, dict) and bool(notice.get('ended'))
        extended = player.get('protected_until', 0) > self.now and not ended
        if extended:
            player['protected_until'] += PROTECTION_SECONDS - LEGACY_PROTECTION_SECONDS
            for report in player.get('reports', []):
                if (report.get('protection_event') == 'started'
                        and report.get('text') == LEGACY_START_TEXT):
                    text = store_text(t(START_TEXT))
                    report['text'] = render_text(text, 'pl')
                    if not isinstance(report.get('i18n'), dict):
                        report['i18n'] = {}
                    report['i18n'].setdefault('title', store_text(t(report['title'])))
                    report['i18n']['text'] = text
        player['protection_duration_version'] = PROTECTION_DURATION_VERSION
        return extended

    def _protection_report(self, player, event, title, text, *, reason='', at=None):
        self._report(player['id'], title, text)
        report = player['reports'][0]
        report['protection_event'] = event
        if reason:
            report['protection_end_reason'] = reason
        if at is not None:
            report['at'] = at

    def _ensure_protection_notice(self, player):
        notice = player.get('protection_notice')
        if isinstance(notice, dict) and notice.get('version') == 1:
            return notice
        active = player.get('protected_until', 0) > self.now
        notice = {'version': 1, 'started': True, 'ended': not active}
        player['protection_notice'] = notice
        if active:
            self._protection_report(player, 'started', t('Ochrona początkującego'), t(START_TEXT))
        return notice

    def _ensure_protection_notices(self):
        for player in self.data['players'].values():
            self._ensure_protection_notice(player)

    def _protection_deadlines(self):
        return [player.get('protected_until', 0)
                for player in self.data['players'].values()
                if not player.get('protection_notice', {}).get('ended', True)]

    def _finish_protection_notice(self, player, reason):
        notice = self._ensure_protection_notice(player)
        if notice['ended']:
            return
        if reason == 'alliance_support':
            intro = t('Ochrona początkującego zakończyła się po wysłaniu wsparcia sojuszu.')
        elif reason == 'hostile_action':
            intro = t('Ochrona początkującego zakończyła się po rozpoczęciu działań przeciw innemu graczowi.')
        else:
            intro = t('Upłynął czas ochrony początkującego.')
        self._protection_report(player, 'ended', t('Ochrona zakończona'), intro + ' ' + t(END_TEXT),
                                reason=reason, at=min(self.now, player.get('protected_until', self.now)))
        notice['ended'] = True

    def _expire_protection_notices(self):
        for player in self.data['players'].values():
            if player.get('protected_until', 0) <= self.now:
                self._finish_protection_notice(player, 'expired')

    def _end_beginner_protection(self, player_id, reason='hostile_action'):
        player = self._player(player_id)
        # A failed fleet launch never reaches this point. The report and the
        # shortened deadline commit or roll back together with the dispatch.
        self._ensure_protection_notice(player)
        was_active = player.get('protected_until', 0) > self.now
        player['protected_until'] = min(player.get('protected_until', 0), self.now)
        self._finish_protection_notice(player, reason if was_active else 'expired')
