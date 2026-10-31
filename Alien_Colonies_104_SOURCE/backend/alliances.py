"""Persistent, permission-checked alliances; all writes share World's transaction.

Recruitment and chat never grant galaxy visibility. Membership, not a supplied
alliance id, authorizes private reads. Departures create a symmetric 24-hour truce
and a joining cooldown; this also applies when the leader disbands an alliance.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
import unicodedata

try:
    from .i18n import t, store_text, render_text
except ImportError:
    from i18n import t, store_text, render_text

MAX_MEMBERS = 20
RECRUITMENT_SECONDS = 7 * 86400
DEPARTURE_SECONDS = 86400
MAX_INVITATIONS = 50
MAX_APPLICATIONS = 100
MAX_CHAT = 100
REQUEST_HISTORY = 200


def _pair(a, b):
    return json.dumps(sorted((a, b)), separators=(',', ':'))


class AllianceMixin:
    def _alliance_error(self, source, status=400):
        raise self.account_error_class(t(source), status)

    def _ensure_alliances(self, data=None):
        data = self.data if data is None else data
        alliances = data.setdefault('alliances', {})
        data.setdefault('alliance_truces', {})
        players = data.setdefault('players', {})
        occupied = set()
        for aid, alliance in sorted(list(alliances.items())):
            alliance.setdefault('id', aid)
            alliance.setdefault('description', '')
            alliance.setdefault('created', self.now)
            alliance.setdefault('invitations', {})
            alliance.setdefault('applications', {})
            alliance.setdefault('chat', [])
            alliance.setdefault('chat_next_id', 1)
            alliance.setdefault('invite_history', {})
            for pid in list(alliance.setdefault('members', {})):
                if pid not in players or pid in occupied:
                    del alliance['members'][pid]
                    continue
                occupied.add(pid)
                member = alliance['members'][pid]
                member.setdefault('joined_at', alliance['created'])
                if member.get('role') not in ('leader', 'officer', 'member'):
                    member['role'] = 'member'
                players[pid]['alliance_id'] = aid
            if not alliance['members']:
                del alliances[aid]
                continue
            leader = alliance.get('leader_id')
            if leader not in alliance['members']:
                leader = self._alliance_successor(alliance)
            alliance['leader_id'] = leader
            for pid, member in alliance['members'].items():
                if pid == leader:
                    member['role'] = 'leader'
                elif member['role'] == 'leader':
                    member['role'] = 'member'
        for pid, player in players.items():
            if pid not in occupied:
                player['alliance_id'] = ''
            player.setdefault('alliance_join_after', 0)
            player.setdefault('alliance_requests', {})
        self._alliance_prune(data)
        data['alliances_schema'] = 1

    def _alliance_prune(self, data=None):
        data = self.data if data is None else data
        players = data.get('players', {})
        for alliance in data.get('alliances', {}).values():
            for key in ('invitations', 'applications'):
                pending = alliance[key]
                for pid, entry in list(pending.items()):
                    if (pid not in players or players[pid].get('alliance_id')
                            or float(entry.get('expires', 0)) <= self.now):
                        del pending[pid]
            alliance['invite_history'] = {
                pid: at for pid, at in alliance.get('invite_history', {}).items()
                if pid in players and at > self.now - 3600}
        data['alliance_truces'] = {
            pair: until for pair, until in data.get('alliance_truces', {}).items()
            if until > self.now}

    def _alliance_for(self, player_id, required=False):
        player = self._player(player_id)
        alliance = self.data.get('alliances', {}).get(player.get('alliance_id', ''))
        if alliance is not None and player_id not in alliance.get('members', {}):
            alliance = None
        if required and alliance is None:
            self._alliance_error('Nie należysz do sojuszu.', 403)
        return alliance

    def _alliance_role(self, player_id):
        alliance = self._alliance_for(player_id)
        return alliance['members'][player_id]['role'] if alliance else ''

    def _alliance_register_chat_visibility(self, player_id):
        """Freeze existing chat IDs at account creation, independent of joining.

        Each alliance has its own monotonic sequence. Keeping the last issued ID
        also handles pruned messages and equal account/message timestamps. Older
        accounts without this field retain their previous access to history.
        """
        self._player(player_id).setdefault('chat_alliance_creation_floors', {
            aid: max(int(alliance.get('chat_next_id', 1)) - 1,
                     max((int(message['id']) for message in alliance.get('chat', [])), default=0))
            for aid, alliance in self.data.get('alliances', {}).items()
        })

    def _allied(self, a, b):
        if not a or not b or a not in self.data['players'] or b not in self.data['players']:
            return False
        alliance = self._alliance_for(a)
        return bool(alliance and b in alliance['members']
                    and self.data['players'][b].get('alliance_id') == alliance['id'])

    def _alliance_attack_block(self, a, b):
        if not isinstance(a, str) or not isinstance(b, str) or not a or not b:
            return False
        return self._allied(a, b) or self.data.get('alliance_truces', {}).get(_pair(a, b), 0) > self.now

    def _alliance_manage(self, pid, leader_only=False):
        alliance = self._alliance_for(pid, True)
        allowed = ('leader',) if leader_only else ('leader', 'officer')
        if alliance['members'][pid]['role'] not in allowed:
            self._alliance_error('Nie masz uprawnień do tej operacji w sojuszu.', 403)
        return alliance

    def _alliance_clean_text(self, value, limit, allow_empty=True, multiline=False):
        if not isinstance(value, str) or len(value) > limit * 4 + 16:
            self._alliance_error('Nieprawidłowy tekst sojuszu.')
        if multiline:
            value = value.replace('\r\n', '\n').replace('\r', '\n').replace('\t', ' ')
        value = unicodedata.normalize('NFKC', value).strip()
        if any(unicodedata.category(c).startswith('C') and not (multiline and c == '\n') for c in value):
            self._alliance_error('Tekst zawiera niedozwolone znaki.')
        if not multiline:
            value = ' '.join(value.split())
        if len(value) > limit or (not allow_empty and not value):
            self._alliance_error('Tekst jest pusty lub zbyt długi.')
        return value

    def _alliance_identity(self, name, tag, description, exclude=''):
        name = self._alliance_clean_text(name, 32, False)
        if len(name) < 3 or not any(c.isalnum() for c in name):
            self._alliance_error('Nazwa sojuszu musi mieć od 3 do 32 znaków.')
        if not isinstance(tag, str) or not re.fullmatch(r'[A-Za-z0-9]{3,5}', tag):
            self._alliance_error('Tag sojuszu musi mieć od 3 do 5 liter A–Z lub cyfr.')
        tag = tag.upper()
        description = self._alliance_clean_text(description, 500, multiline=True)
        for aid, existing in self.data.get('alliances', {}).items():
            if aid != exclude and (existing['name'].casefold() == name.casefold() or existing['tag'] == tag):
                self._alliance_error('Nazwa lub tag sojuszu są już zajęte.', 409)
        return name, tag, description

    def _alliance_can_join(self, pid):
        player = self._player(pid)
        if self._alliance_for(pid):
            self._alliance_error('To imperium już należy do sojuszu.', 409)
        if player.get('alliance_join_after', 0) > self.now:
            self._alliance_error('Po opuszczeniu sojuszu trzeba odczekać 24 godziny przed kolejnym dołączeniem.', 409)

    def _alliance_target(self, payload):
        pid = payload.get('player_id')
        if pid is not None:
            if not isinstance(pid, str) or pid not in self.data['players']:
                self._alliance_error('Nie znaleziono imperium.', 404)
            return pid
        name = self._alliance_clean_text(payload.get('player_name'), 32, False)
        for player_id, player in self.data['players'].items():
            if unicodedata.normalize('NFKC', player['name']).casefold() == name.casefold():
                return player_id
        self._alliance_error('Nie znaleziono imperium.', 404)

    def _alliance_by_id(self, payload):
        aid = payload.get('alliance_id')
        if not isinstance(aid, str) or aid not in self.data.get('alliances', {}):
            self._alliance_error('Nie znaleziono sojuszu.', 404)
        return self.data['alliances'][aid]

    def _alliance_clear_recruitment(self, pid):
        for alliance in self.data.get('alliances', {}).values():
            alliance['invitations'].pop(pid, None)
            alliance['applications'].pop(pid, None)

    def _alliance_join(self, pid, alliance, role='member'):
        self._alliance_can_join(pid)
        if len(alliance['members']) >= MAX_MEMBERS:
            self._alliance_error('Sojusz osiągnął limit 20 członków.', 409)
        alliance['members'][pid] = {'role': role, 'joined_at': self.now}
        self._player(pid)['alliance_id'] = alliance['id']
        self._alliance_clear_recruitment(pid)
        hook = getattr(self, '_alliance_member_joined', None)
        if hook:
            hook(pid, alliance['id'])

    @staticmethod
    def _alliance_successor(alliance):
        return min(alliance['members'], key=lambda pid: (
            alliance['members'][pid].get('role') != 'officer',
            alliance['members'][pid].get('joined_at', 0), pid))

    def _alliance_depart(self, pid, alliance, deleted=False):
        hook = getattr(self, '_alliance_member_departed', None)
        if hook:
            hook(pid, alliance['id'])
        if not deleted:
            until = self.now + DEPARTURE_SECONDS
            player = self._player(pid)
            player['alliance_join_after'] = max(player.get('alliance_join_after', 0), until)
            for peer in alliance['members']:
                if peer != pid:
                    key = _pair(pid, peer)
                    self.data['alliance_truces'][key] = max(self.data['alliance_truces'].get(key, 0), until)
        self._player(pid)['alliance_id'] = ''
        del alliance['members'][pid]
        self._alliance_clear_recruitment(pid)
        if not alliance['members']:
            self.data['alliances'].pop(alliance['id'], None)
        elif alliance['leader_id'] == pid:
            leader = self._alliance_successor(alliance)
            alliance['leader_id'] = leader
            alliance['members'][leader]['role'] = 'leader'

    def _alliance_account_delete(self, pid):
        alliance = self._alliance_for(pid)
        if alliance:
            self._alliance_depart(pid, alliance, deleted=True)
        self._alliance_clear_recruitment(pid)
        for remaining in self.data.get('alliances', {}).values():
            remaining['chat'] = [m for m in remaining['chat'] if m['sender_id'] != pid]
            remaining.get('invite_history', {}).pop(pid, None)
            for entry in remaining['invitations'].values():
                if entry.get('invited_by') == pid:
                    entry['invited_by'] = ''
        self.data['alliance_truces'] = {
            key: until for key, until in self.data.get('alliance_truces', {}).items()
            if pid not in json.loads(key)}

    def _alliance_public(self, alliance):
        leader = self.data['players'].get(alliance['leader_id'], {})
        return {key: copy.deepcopy(alliance[key]) for key in (
            'id', 'name', 'tag', 'description', 'leader_id', 'created')} | {
            'leader_name': leader.get('name', ''), 'members_count': len(alliance['members']),
            'max_members': MAX_MEMBERS}

    def _alliance_pending_for(self, pid, key):
        result = []
        for alliance in self.data.get('alliances', {}).values():
            item = alliance[key].get(pid)
            if item and item['expires'] > self.now:
                result.append({**self._alliance_public(alliance), **copy.deepcopy(item),
                               'alliance_id': alliance['id']})
        return sorted(result, key=lambda item: (-item['created'], item['id']))

    def alliance_summary(self, player_id):
        with self.lock:
            self._player(player_id)
            alliance = self._alliance_for(player_id)
            result = {'available': True, 'id': '', 'name': '', 'tag': '', 'role': '',
                      'members_count': 0, 'invitations_count': sum(
                          1 for item in self.data.get('alliances', {}).values()
                          if item['invitations'].get(player_id, {}).get('expires', 0) > self.now)}
            if alliance:
                result.update({key: alliance[key] for key in ('id', 'name', 'tag')})
                result.update(role=alliance['members'][player_id]['role'], members_count=len(alliance['members']))
            return result

    def alliance_view(self, player_id, search=''):
        with self.lock:
            player = self._player(player_id)
            search = self._alliance_clean_text(search, 64).casefold()
            alliance = self._alliance_for(player_id)
            own = None
            if alliance:
                own = self._alliance_public(alliance)
                own['role'] = alliance['members'][player_id]['role']
                own['members'] = [{
                    'id': pid, 'player_id': pid, 'name': self.data['players'][pid]['name'],
                    'race_id': self.data['players'][pid].get('race_id', ''),
                    'role': member['role'], 'joined_at': member['joined_at']}
                    for pid, member in sorted(alliance['members'].items(), key=lambda pair: (
                        ('leader', 'officer', 'member').index(pair[1]['role']),
                        pair[1]['joined_at'], pair[0]))]
                chat_floor = player.get('chat_alliance_creation_floors', {}).get(alliance['id'], 0)
                own['chat'] = [dict(m, sender_name=self.data['players'].get(m['sender_id'], {}).get('name', ''))
                               for m in alliance['chat'][-MAX_CHAT:] if m['id'] > chat_floor]
                if own['role'] in ('leader', 'officer'):
                    for key in ('invitations', 'applications'):
                        own[key] = [{**copy.deepcopy(entry), 'player_id': pid,
                                     'player_name': self.data['players'][pid]['name']}
                                    for pid, entry in alliance[key].items()
                                    if pid in self.data['players'] and entry['expires'] > self.now]
            directory = sorted((a for a in self.data.get('alliances', {}).values()
                                if not search or search in (a['name'] + ' ' + a['tag']).casefold()),
                               key=lambda a: (a['tag'], a['id']))
            return {'ok': True, 'alliance': own,
                    'directory': [self._alliance_public(a) for a in directory[:100]],
                    'directory_total': len(directory), 'invitations': self._alliance_pending_for(player_id, 'invitations'),
                    'applications': self._alliance_pending_for(player_id, 'applications'),
                    'cooldown_until': player.get('alliance_join_after', 0),
                    'server_time': self.now, 'rules': {'max_members': MAX_MEMBERS,
                        'departure_cooldown_seconds': DEPARTURE_SECONDS,
                        'former_member_truce_seconds': DEPARTURE_SECONDS,
                        'recruitment_expires_seconds': RECRUITMENT_SECONDS}}

    def alliance_action(self, player_id, payload):
        with self.lock, self._atomic():
            player = self._player(player_id)
            if not isinstance(payload, dict):
                self._alliance_error('Nieprawidłowe polecenie sojuszu.')
            request_id = payload.get('request_id')
            if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
                self._alliance_error('Nieprawidłowy identyfikator polecenia.')
            try:
                encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
            except (TypeError, ValueError, RecursionError):
                self._alliance_error('Polecenie zawiera nieprawidłowe wartości.')
            if len(encoded) > 4096:
                self._alliance_error('Polecenie sojuszu jest zbyt długie.')
            fingerprint = hashlib.sha256(encoded.encode('utf-8')).hexdigest()
            requests = player.setdefault('alliance_requests', {})
            old = requests.get(request_id)
            if old:
                if old['fingerprint'] != fingerprint:
                    self._alliance_error('Ten identyfikator został użyty dla innego polecenia.', 409)
                # A retry cannot keep using a former role or the private channel
                # of a former alliance. Transition acknowledgements (leave,
                # disband, transfer) still remain safe and idempotent.
                self._alliance_retry_authorized(player_id, payload.get('action'), old)
                return dict(self.alliance_view(player_id), message=render_text(old['message']))
            recent = [at for at in player.get('alliance_action_times', []) if at > self.now - 60]
            if len(recent) >= 60:
                self._alliance_error('Zbyt wiele poleceń sojuszu. Spróbuj ponownie za chwilę.', 429)
            self._alliance_prune()
            action = payload.get('action')
            if not isinstance(action, str):
                self._alliance_error('Nieprawidłowe polecenie sojuszu.')
            method = getattr(self, '_alliance_do_' + action, None)
            if method is None:
                self._alliance_error('Nieznane polecenie sojuszu.')
            original_alliance = player.get('alliance_id', '')
            message = method(player_id, payload)
            requests[request_id] = {'fingerprint': fingerprint, 'message': store_text(message),
                                    'alliance_id': original_alliance or player.get('alliance_id', '')}
            while len(requests) > REQUEST_HISTORY:
                del requests[next(iter(requests))]
            player['alliance_action_times'] = recent + [self.now]
            self._touch_player_activity(player_id)
            return dict(self.alliance_view(player_id), message=message)

    def _alliance_retry_authorized(self, pid, action, old):
        managers = ('invite', 'cancel_invite', 'approve_application', 'reject_application', 'kick')
        leaders = ('edit', 'set_role')
        if action in managers + leaders + ('chat_send', 'transfer_leader'):
            alliance = self._alliance_for(pid, True)
            if alliance['id'] != old.get('alliance_id'):
                self._alliance_error('Nie masz dostępu do poprzedniego sojuszu.', 403)
            if action in managers + leaders:
                self._alliance_manage(pid, action in leaders)

    def _alliance_do_create(self, pid, payload):
        self._alliance_can_join(pid)
        name, tag, description = self._alliance_identity(payload.get('name'), payload.get('tag'), payload.get('description', ''))
        aid = 'a' + secrets.token_hex(8)
        alliance = {'id': aid, 'name': name, 'tag': tag, 'description': description,
                    'leader_id': pid, 'created': self.now, 'members': {},
                    'invitations': {}, 'applications': {}, 'chat': [], 'chat_next_id': 1,
                    'invite_history': {}}
        self.data.setdefault('alliances', {})[aid] = alliance
        self.data.setdefault('alliance_truces', {})
        self._alliance_join(pid, alliance, 'leader')
        return t('Utworzono sojusz.')

    def _alliance_do_apply(self, pid, payload):
        self._alliance_can_join(pid)
        alliance = self._alliance_by_id(payload)
        if len(alliance['members']) >= MAX_MEMBERS:
            self._alliance_error('Sojusz osiągnął limit 20 członków.', 409)
        if pid in alliance['applications']:
            self._alliance_error('Podanie do tego sojuszu już oczekuje na decyzję.', 409)
        own = self._player(pid)
        if own.get('alliance_apply_after', 0) > self.now:
            self._alliance_error('Odczekaj minutę przed kolejnym podaniem.', 429)
        if len(self._alliance_pending_for(pid, 'applications')) >= 5 or len(alliance['applications']) >= MAX_APPLICATIONS:
            self._alliance_error('Osiągnięto limit oczekujących podań.', 409)
        text = self._alliance_clean_text(payload.get('text', ''), 300, multiline=True)
        alliance['applications'][pid] = {'text': text, 'created': self.now, 'expires': self.now + RECRUITMENT_SECONDS}
        own['alliance_apply_after'] = self.now + 60
        return t('Wysłano podanie do sojuszu.')

    def _alliance_do_withdraw_application(self, pid, payload):
        alliance = self._alliance_by_id(payload)
        if not alliance['applications'].pop(pid, None):
            self._alliance_error('Nie znaleziono aktualnego podania.', 404)
        return t('Wycofano podanie.')

    def _alliance_do_invite(self, pid, payload):
        alliance = self._alliance_manage(pid)
        target = self._alliance_target(payload)
        self._alliance_can_join(target)
        if len(alliance['members']) >= MAX_MEMBERS:
            self._alliance_error('Sojusz osiągnął limit 20 członków.', 409)
        if target in alliance['invitations']:
            self._alliance_error('Zaproszenie dla tego imperium już oczekuje.', 409)
        if alliance['invite_history'].get(target, 0) > self.now - 60:
            self._alliance_error('Odczekaj minutę przed ponownym zaproszeniem tego imperium.', 429)
        if (len(alliance['invitations']) >= MAX_INVITATIONS or len(alliance['invite_history']) >= 50
                or len(self._alliance_pending_for(target, 'invitations')) >= 20):
            self._alliance_error('Osiągnięto limit oczekujących zaproszeń.', 409)
        alliance['invitations'][target] = {'invited_by': pid, 'created': self.now, 'expires': self.now + RECRUITMENT_SECONDS}
        alliance['invite_history'][target] = self.now
        return t('Wysłano zaproszenie do sojuszu.')

    def _alliance_do_accept_invite(self, pid, payload):
        alliance = self._alliance_by_id(payload)
        if pid not in alliance['invitations']:
            self._alliance_error('Zaproszenie wygasło lub zostało wycofane.', 409)
        self._alliance_join(pid, alliance)
        return t('Dołączono do sojuszu.')

    def _alliance_do_decline_invite(self, pid, payload):
        alliance = self._alliance_by_id(payload)
        if not alliance['invitations'].pop(pid, None):
            self._alliance_error('Zaproszenie wygasło lub zostało wycofane.', 409)
        return t('Odrzucono zaproszenie.')

    def _alliance_do_cancel_invite(self, pid, payload):
        alliance = self._alliance_manage(pid)
        target = self._alliance_target(payload)
        if not alliance['invitations'].pop(target, None):
            self._alliance_error('Zaproszenie wygasło lub zostało wycofane.', 409)
        return t('Wycofano zaproszenie.')

    def _alliance_do_approve_application(self, pid, payload):
        alliance = self._alliance_manage(pid)
        target = self._alliance_target(payload)
        if target not in alliance['applications']:
            self._alliance_error('Nie znaleziono aktualnego podania.', 404)
        self._alliance_join(target, alliance)
        return t('Przyjęto nowe imperium do sojuszu.')

    def _alliance_do_reject_application(self, pid, payload):
        alliance = self._alliance_manage(pid)
        target = self._alliance_target(payload)
        if not alliance['applications'].pop(target, None):
            self._alliance_error('Nie znaleziono aktualnego podania.', 404)
        return t('Odrzucono podanie.')

    def _alliance_do_kick(self, pid, payload):
        alliance = self._alliance_manage(pid)
        target = self._alliance_target(payload)
        member = alliance['members'].get(target)
        if not member:
            self._alliance_error('To imperium nie należy do twojego sojuszu.', 404)
        if (target == pid or member['role'] == 'leader'
                or (self._alliance_role(pid) == 'officer' and member['role'] != 'member')):
            self._alliance_error('Nie możesz usunąć tego członka sojuszu.', 403)
        self._alliance_depart(target, alliance)
        return t('Usunięto członka sojuszu. Obowiązuje wzajemny rozejm przez 24 godziny.')

    def _alliance_do_set_role(self, pid, payload):
        alliance = self._alliance_manage(pid, True)
        target, role = self._alliance_target(payload), payload.get('role')
        if target not in alliance['members'] or target == pid or role not in ('officer', 'member'):
            self._alliance_error('Nieprawidłowa zmiana roli w sojuszu.')
        alliance['members'][target]['role'] = role
        return t('Zmieniono rolę członka sojuszu.')

    def _alliance_do_transfer_leader(self, pid, payload):
        alliance = self._alliance_manage(pid, True)
        target = self._alliance_target(payload)
        if target == pid or target not in alliance['members']:
            self._alliance_error('Wybierz innego członka sojuszu jako przywódcę.')
        alliance['members'][pid]['role'] = 'officer'
        alliance['members'][target]['role'] = 'leader'
        alliance['leader_id'] = target
        return t('Przekazano przywództwo sojuszu.')

    def _alliance_do_edit(self, pid, payload):
        alliance = self._alliance_manage(pid, True)
        name, tag, description = self._alliance_identity(payload.get('name', alliance['name']),
            payload.get('tag', alliance['tag']), payload.get('description', alliance['description']), alliance['id'])
        alliance.update(name=name, tag=tag, description=description)
        return t('Zapisano dane sojuszu.')

    def _alliance_do_leave(self, pid, payload):
        alliance = self._alliance_for(pid, True)
        if alliance['leader_id'] == pid and len(alliance['members']) > 1:
            self._alliance_error('Przed odejściem przekaż przywództwo innemu członkowi.', 409)
        self._alliance_depart(pid, alliance)
        return t('Opuszczono sojusz. Przez 24 godziny trwa rozejm i blokada dołączenia do innego sojuszu.')

    def _alliance_do_disband(self, pid, payload):
        alliance = self._alliance_manage(pid, True)
        if payload.get('confirmation') != alliance['tag']:
            self._alliance_error('Wpisz dokładny tag sojuszu, aby potwierdzić rozwiązanie.')
        for member in list(alliance['members']):
            self._alliance_depart(member, alliance)
        return t('Rozwiązano sojusz. Byłych członków obowiązuje rozejm przez 24 godziny.')

    def _alliance_do_chat_send(self, pid, payload):
        alliance = self._alliance_for(pid, True)
        text = self._alliance_clean_text(payload.get('text'), 500, False, multiline=True)
        if text.count('\n') > 8:
            self._alliance_error('Wiadomość może mieć od 1 do 500 znaków.')
        if not self._chat_permissions(pid, '')['can_send']:
            self._alliance_error('Wysyłanie wiadomości jest obecnie zablokowane.', 403)
        player = self._player(pid)
        if player.get('alliance_chat_after', 0) > self.now:
            self._alliance_error('Odczekaj chwilę przed kolejną wiadomością.', 429)
        alliance['chat'].append({'id': alliance['chat_next_id'], 'sender_id': pid, 'text': text, 'at': self.now})
        alliance['chat_next_id'] += 1
        alliance['chat'] = alliance['chat'][-MAX_CHAT:]
        player['alliance_chat_after'] = self.now + 2
        return t('Wysłano wiadomość do sojuszu.')
