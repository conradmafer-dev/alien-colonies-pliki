"""Persistent alliance fleets and mixed-faction combat.

The ordinary solo resolver stays untouched. Every coalition formation retains its
owner's stats. Simultaneous salvos are spread in proportion to each formation's
remaining effective hull at the opening of the round; low-hull units absorb hits
within that formation. One engagement has one resource pool and one Khar quota.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import secrets

try:
    from . import battle_replay, defenses, swarm
    from .races import SHIP_TRAITS
    from .fleet_expansion import COMBAT_ROLES
    from .i18n import t, store_text, render_text
except ImportError:
    import battle_replay, defenses, swarm
    from races import SHIP_TRAITS
    from fleet_expansion import COMBAT_ROLES
    from i18n import t, store_text, render_text

RESOURCES = ('metal', 'crystal', 'fuel')
COMBAT_SHIPS = COMBAT_ROLES
ACTIVE = ('forming',)


def capacity(specs, ships):
    return math.floor(round(math.fsum(specs[k][6] * n for k, n in ships.items() if n), 6))


def apportion(amount, weights, limits=None):
    """Integer largest-remainder allocation with hard capacities; no lost units.

    Keys have an explicit deterministic order. Saturated recipients are removed
    and their excess is offered to the other positive-weight recipients.
    """
    keys = sorted(weights)
    limits = {k: max(0, int((limits or {}).get(k, amount))) for k in keys}
    result = dict.fromkeys(keys, 0)
    remaining = max(0, int(amount))
    while remaining:
        active = [k for k in keys if weights[k] > 0 and result[k] < limits[k]]
        total = sum(weights[k] for k in active)
        if not active or total <= 0:
            break
        exact = {k: remaining * weights[k] / total for k in active}
        given = 0
        for k in active:
            n = min(limits[k] - result[k], int(math.floor(exact[k])))
            result[k] += n
            given += n
        remaining -= given
        if remaining:
            for k in sorted(active, key=lambda k: (-(exact[k] - math.floor(exact[k])), k)):
                if result[k] < limits[k] and remaining:
                    result[k] += 1
                    remaining -= 1
                    given += 1
        if not given:
            break
    return result


class AllianceOperationsMixin:
    def _ensure_alliance_operations(self, data=None):
        data = self.data if data is None else data
        data.setdefault('alliance_operations', {})
        data.setdefault('alliance_operation_requests', {})
        data.setdefault('alliance_operations_schema', 1)

    def _operation_error(self, message, status=409):
        raise self.account_error_class(message, status)

    def _operation_membership(self, player_id):
        self._player(player_id)
        alliance = self._alliance_for(player_id)
        if not alliance:
            self._operation_error(t('Najpierw dołącz do sojuszu.'), 403)
        return alliance

    def _operation_lookup(self, player_id, operation_id):
        alliance = self._operation_membership(player_id)
        operation = self.data.get('alliance_operations', {}).get(operation_id) if isinstance(operation_id, str) else None
        if not operation or operation['alliance_id'] != alliance['id']:
            self._operation_error(t('Operacja jest niedostępna.'), 404)
        return operation

    def _operation_known_targets(self, player_id):
        galaxy, _ = self._public_observation_map(player_id)
        return {p['id']: p for s in galaxy for p in s['planets']}

    def _operation_target_allowed(self, owner, target):
        if target['owner_type'] not in ('alien', 'player') or target['owner_id'] == owner:
            return False
        if target['owner_type'] == 'player':
            other = self.data['players'].get(target['owner_id'])
            if not other or other.get('protected_until', 0) > self.now:
                return False
            if self._alliance_attack_block(owner, target['owner_id']):
                return False
        return True

    def _operation_ship_specs(self, owner, *, stored=False):
        race = self._race_id(owner)
        return [{'key': k, ('name_i18n' if stored else 'name'): store_text(v[0]) if stored else v[0],
                 'art_key': 'races/' + race + '/' + k if race else k}
                for k, v in self._specs(owner, 'ships').items()]

    def alliance_operations_view(self, player_id):
        with self.lock:
            alliance = self._operation_membership(player_id)
            result = {'ok': True, 'server_time': self.now, 'operations': [], 'supports': [],
                      'origins': [], 'defense_targets': [], 'attack_targets': []}
            for p in self.data['planets'].values():
                if p['owner_id'] == player_id:
                    result['origins'].append({'id': p['id'], 'name': p['name'], 'ships': dict(p['ships']),
                                               'ship_specs': self._operation_ship_specs(player_id)})
                elif self._allied(player_id, p['owner_id']):
                    result['defense_targets'].append({'id': p['id'], 'name': p['name'],
                                                       'owner_name': self._player(p['owner_id'])['name']})
            for p in self._operation_known_targets(player_id).values():
                if p.get('owner_type') in ('alien', 'player') and p.get('owner_id') != player_id and not self._allied(player_id, p.get('owner_id', '')):
                    result['attack_targets'].append({k: p.get(k, '') for k in ('id', 'name', 'owner_name')})
            for op in sorted(self.data.get('alliance_operations', {}).values(), key=lambda x: x['created_at'], reverse=True):
                if op['alliance_id'] != alliance['id']:
                    continue
                participants = []
                for item in op['participants'].values():
                    fleet = self.data['fleets'].get(item['fleet_id'])
                    entry = copy.deepcopy(item)
                    for spec in entry.get('ship_specs', []):
                        if 'name_i18n' in spec:
                            spec['name'] = render_text(spec.pop('name_i18n'))
                    if fleet:
                        entry.update(ships=dict(fleet['ships']), status=fleet['status'])
                    participants.append(entry)
                joined = any(x['owner_id'] == player_id and x.get('status') == 'outbound' for x in participants)
                active = op['status'] in ACTIVE
                result['operations'].append({k: copy.deepcopy(op[k]) for k in
                    ('id', 'creator_id', 'target', 'impact_at', 'created_at', 'status')})
                if op.get('known_swarm'):
                    result['operations'][-1]['target']['owner_name'] = t('Rój Khar')
                result['operations'][-1].update(participants=participants,
                    can_join=active and not joined and self.now < op['impact_at'] - 30 and len(op['participants']) < 5,
                    can_withdraw=active and joined,
                    can_cancel=active and (op['creator_id'] == player_id or self._alliance_role(player_id) == 'leader'),
                    result=copy.deepcopy(op.get('result', {})))
            for f in self.data['fleets'].values():
                if f['mission'] != 'alliance_defense' or f.get('alliance_id') != alliance['id']:
                    continue
                origin = self.data['planets'].get(f['origin_id'], {})
                result['supports'].append({'fleet_id': f['id'], 'owner_id': f['owner_id'],
                    'owner_name': self.data['players'].get(f['owner_id'], {}).get('name', ''),
                    'target_id': f['target_id'], 'target_name': f['target_name'],
                    'origin_id': f['origin_id'], 'origin_name': origin.get('name', ''),
                    'ships': dict(f['ships']), 'ship_specs': self._operation_ship_specs(f['owner_id']),
                    'status': f['status'], 'arrives_at': f['arrives_at'], 'hold_until': f['hold_until'],
                    'can_recall': f['owner_id'] == player_id and f['status'] != 'returning'})
            return result

    def _operation_quote(self, player_id, payload):
        alliance = self._operation_membership(player_id)
        if not isinstance(payload, dict) or payload.get('action') not in ('join', 'defend'):
            self._operation_error(t('Wybierz udział w ataku albo wsparcie obrony.'), 400)
        if payload.get('travel_mode', 'normal') != 'normal':
            self._operation_error(t('Operacje sojuszu korzystają ze zwykłego lotu, bez tunelu.'), 400)
        origin = self._owned(player_id, payload.get('planet_id'))
        operation = None
        hold = 0
        if payload['action'] == 'join':
            operation = self._operation_lookup(player_id, payload.get('operation_id'))
            if operation['status'] not in ACTIVE or self.now >= operation['impact_at'] - 30:
                self._operation_error(t('Dołączanie do tej operacji zostało zamknięte.'))
            if player_id in operation['participants'] or len(operation['participants']) >= 5:
                self._operation_error(t('Operacja mieści pięć imperiów, po jednej flocie każdego z nich.'))
            target = self.data['planets'][operation['target']['id']]
            if not self._operation_target_allowed(player_id, target):
                self._operation_error(t('Cel nie może zostać zaatakowany.'), 403)
        else:
            target_id = payload.get('target_id')
            target = self.data['planets'].get(target_id) if isinstance(target_id, str) else None
            if not target or target['owner_id'] == player_id or not self._allied(player_id, target['owner_id']):
                self._operation_error(t('Wsparcie można wysłać tylko na planetę innego członka sojuszu.'), 403)
            if self._player(target['owner_id']).get('protected_until', 0) > self.now:
                self._operation_error(t('Nie można stacjonować wsparcia pod ochroną startową sojusznika.'), 403)
            hold = payload.get('hold_hours', 1)
            if type(hold) is not int or hold not in (1, 4, 8):
                self._operation_error(t('Wybierz dyżur obronny na 1, 4 albo 8 godzin.'), 400)
            supports = [f for f in self.data['fleets'].values() if f['mission'] == 'alliance_defense'
                        and f['target_id'] == target['id'] and f['status'] != 'returning']
            if len(supports) >= 5 or any(f['owner_id'] == player_id for f in supports):
                self._operation_error(t('Planetę może wspierać pięć imperiów, po jednej flocie każdego z nich.'))
        raw = payload.get('ships')
        specs = self._specs(player_id, 'ships')
        if not isinstance(raw, dict) or any(k not in specs for k in raw):
            self._operation_error(t('Nieprawidłowy skład floty.'), 400)
        ships = {}
        for k in specs:
            n = raw.get(k, 0)
            if type(n) is not int or not 0 <= n <= 10000:
                self._operation_error(t('Nieprawidłowy skład floty.'), 400)
            if n > origin['ships'].get(k, 0):
                self._operation_error(t('Nie masz tylu statków na tej planecie.'))
            ships[k] = n
        if not any(ships.get(k, 0) for k in COMBAT_SHIPS):
            self._operation_error(t('Operacja wymaga przynajmniej jednego okrętu bojowego.'), 400)
        if sum(f['owner_id'] == player_id for f in self.data['fleets'].values()) >= 8:
            self._operation_error(t('Możesz prowadzić najwyżej 8 misji naraz.'))
        seconds, fuel = self._flight_numbers(origin, target, ships, self._player(player_id)['research']['propulsion'])
        # ACS-style holding costs one tenth of the fuel coefficient per hour.
        # Racial/skill/research factors already belong to spec[7]; apply the
        # launch colony's discount once, just as for the prepaid flight.
        local_fuel_factor = 1 - self._building_effects(origin).get('fleet_fuel_reduction', 0)
        upkeep = math.ceil(round(math.fsum(specs[k][7] * n for k, n in ships.items())
                                 * hold * .1 * local_fuel_factor, 6))
        fuel += upkeep
        if operation and self.now + seconds > operation['impact_at']:
            self._operation_error(t('Ta flota nie zdąży dotrzeć przed ustalonym uderzeniem.'))
        affordable = origin['resources']['fuel'] >= fuel
        return {'origin': origin, 'target': target, 'ships': ships, 'operation': operation,
                'alliance_id': alliance['id'], 'seconds': seconds, 'fuel_cost': fuel,
                'upkeep': upkeep, 'capacity': capacity(specs, ships), 'hold_hours': hold,
                'affordable': affordable, 'shortfall': {'fuel': max(0, math.ceil(fuel - origin['resources']['fuel']))}}

    def alliance_operation_preview(self, player_id, payload):
        with self.lock:
            q = self._operation_quote(player_id, payload)
            return {'ok': True, **{k: q[k] for k in ('seconds', 'fuel_cost', 'capacity', 'affordable', 'shortfall', 'hold_hours')},
                    'impact_at': q['operation']['impact_at'] if q['operation'] else self.now + q['seconds'],
                    'protection_warning': q['target']['owner_type'] == 'player',
                    'message': t('Koszt obejmuje lot w obie strony i cały dyżur. Niewykorzystane paliwo nie jest zwracane.') if q['hold_hours'] else t('Koszt obejmuje lot w obie strony. Czas uderzenia jest stały.'),
                    'upkeep_fuel': q['upkeep']}

    def alliance_operation(self, player_id, payload):
        with self.lock, self._atomic():
            self._ensure_alliance_operations()
            self._player(player_id)
            if not isinstance(payload, dict):
                self._operation_error(t('Nieprawidłowe dane operacji.'), 400)
            request_id = payload.get('request_id')
            if not isinstance(request_id, str) or not 8 <= len(request_id) <= 96 or not all(c.isalnum() or c in '-_' for c in request_id):
                self._operation_error(t('Operacja wymaga poprawnego identyfikatora żądania.'), 400)
            try:
                encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
            except (TypeError, ValueError, RecursionError):
                self._operation_error(t('Nieprawidłowe dane operacji.'), 400)
            if len(encoded) > 8192:
                self._operation_error(t('Nieprawidłowe dane operacji.'), 400)
            fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
            requests = self.data['alliance_operation_requests'].setdefault(player_id, {})
            previous = requests.get(request_id)
            alliance = self._operation_membership(player_id)
            if previous:
                if previous.get('alliance_id') != alliance['id']:
                    self._operation_error(t('Operacja jest niedostępna.'), 403)
                if payload.get('action') == 'create' and self._alliance_role(player_id) not in ('leader', 'officer'):
                    self._operation_error(t('Operację może utworzyć lider lub oficer.'), 403)
                if previous['fingerprint'] != fingerprint:
                    self._operation_error(t('Ten identyfikator został już użyty do innej operacji.'))
                response = copy.deepcopy(previous['response'])
                response['message'] = render_text(response['message'])
                return response
            alliance = self._operation_membership(player_id)
            action = payload.get('action')
            response = {'ok': True}
            if action == 'create':
                if self._alliance_role(player_id) not in ('leader', 'officer'):
                    self._operation_error(t('Operację może utworzyć lider lub oficer.'), 403)
                delay = payload.get('delay_seconds', 900)
                if type(delay) is not int or not 300 <= delay <= 86400:
                    self._operation_error(t('Uderzenie zaplanuj za 5 minut do 24 godzin.'), 400)
                if sum(op['alliance_id'] == alliance['id'] and op['status'] in ACTIVE for op in self.data['alliance_operations'].values()) >= 3:
                    self._operation_error(t('Sojusz może prowadzić trzy aktywne operacje.'))
                target_id = payload.get('target_id')
                known = self._operation_known_targets(player_id).get(target_id) if isinstance(target_id, str) else None
                target = self.data['planets'].get(target_id) if known else None
                if not target or not self._operation_target_allowed(player_id, target):
                    self._operation_error(t('Wybierz znany, dostępny cel ataku.'), 403)
                opid = 'op_' + secrets.token_hex(12)
                op = {'id': opid, 'alliance_id': alliance['id'], 'creator_id': player_id,
                      'created_at': self.now, 'impact_at': self.now + delay, 'status': 'forming', 'participants': {},
                      'target': {k: known.get(k, '') for k in ('id', 'name', 'owner_name')},
                      'target_owner_id': target['owner_id'], 'known_swarm': known.get('owner_id') == 'khar'}
                self.data['alliance_operations'][opid] = op
                response.update(operation_id=opid, message=t('Operacja utworzona. Każdy uczestnik sam wysyła swoją flotę.'))
            elif action in ('join', 'defend'):
                q = self._operation_quote(player_id, payload)
                if not q['affordable']:
                    self._operation_error(t('Brakuje paliwa na lot i dyżur obronny.'))
                p, target, op = q['origin'], q['target'], q['operation']
                p['resources']['fuel'] -= q['fuel_cost']
                for k, n in q['ships'].items():
                    p['ships'][k] -= n
                fid = 'af_' + secrets.token_hex(12)
                arrives = op['impact_at'] if op else self.now + q['seconds']
                effects = self._building_effects(p)
                effects.pop('renewal_fraction', None)
                f = {'id': fid, 'owner_id': player_id, 'race_id': self._race_id(player_id),
                     'origin_id': p['id'], 'target_id': target['id'], 'target_name': op['target']['name'] if op else target['name'],
                     'mission': 'alliance_attack' if op else 'alliance_defense', 'status': 'outbound',
                     'ships': q['ships'], 'cargo': dict.fromkeys(RESOURCES, 0), 'swarm_crystals': 0,
                     'started_at': self.now, 'seconds': arrives - self.now, 'return_seconds': q['seconds'],
                     'arrives_at': arrives, 'fuel_paid': q['fuel_cost'], 'building_effects': effects,
                     'alliance_id': alliance['id'], 'route': self._route_details(p, target)}
                if op:
                    f['operation_id'] = op['id']
                    op['participants'][player_id] = {'owner_id': player_id, 'owner_name': self._player(player_id)['name'],
                        'fleet_id': fid, 'origin_name': p['name'], 'ships': dict(f['ships']), 'status': 'outbound',
                        'ship_specs': self._operation_ship_specs(player_id, stored=True)}
                else:
                    f.update(hold_hours=q['hold_hours'], hold_until=arrives + q['hold_hours'] * 3600,
                             support_owner_id=target['owner_id'])
                self.data['fleets'][fid] = f
                if not op or target['owner_type'] == 'player':
                    self._end_beginner_protection(player_id, 'hostile_action' if op else 'alliance_support')
                if op and target['owner_type'] == 'player':
                    self._report(target['owner_id'], t('Nadciąga atak sojuszu'),
                        t('Imperium {0} dołączyło do ataku na {1}. Uderzenie za {2} s.').format(self._player(player_id)['name'], target['name'], int(arrives - self.now)))
                elif not op:
                    self._report(target['owner_id'], t('Nadciąga wsparcie sojuszu'),
                        t('Imperium {0} wysłało wsparcie obrony na {1}. Dyżur: {2} godz.').format(self._player(player_id)['name'], target['name'], q['hold_hours']))
                response.update(fleet_id=fid, message=t('Flota sojuszu wyruszyła. Paliwo pobrano raz przy starcie.'))
            elif action in ('withdraw', 'cancel'):
                op = self._operation_lookup(player_id, payload.get('operation_id'))
                if op['status'] not in ACTIVE:
                    self._operation_error(t('Ta operacja jest już zakończona.'))
                if action == 'cancel':
                    if player_id != op['creator_id'] and self._alliance_role(player_id) != 'leader':
                        self._operation_error(t('Operację może odwołać jej organizator lub lider.'), 403)
                    self._operation_cancel(op)
                else:
                    item = op['participants'].get(player_id)
                    f = self.data['fleets'].get(item['fleet_id']) if item else None
                    if not f or f['status'] != 'outbound':
                        self._operation_error(t('Twoja flota nie uczestniczy w tej operacji.'))
                    self._operation_return(f, early=True)
                    del op['participants'][player_id]
                    if not op['participants']:
                        self._operation_cancel(op)
                response['message'] = t('Odwołane floty wracają do własnych kolonii.')
            elif action == 'recall':
                fid = payload.get('fleet_id')
                f = self.data['fleets'].get(fid) if isinstance(fid, str) else None
                if not f or f['owner_id'] != player_id or f['mission'] != 'alliance_defense' or f['status'] == 'returning':
                    self._operation_error(t('Nie możesz odwołać tej floty.'), 403)
                self._operation_return(f, early=f['status'] == 'outbound')
                response['message'] = t('Wsparcie wraca do własnej kolonii.')
            else:
                self._operation_error(t('Nieznana operacja sojuszu.'), 400)
            stored_response = copy.deepcopy(response)
            stored_response['message'] = store_text(response['message'])
            requests[request_id] = {'fingerprint': fingerprint, 'response': stored_response, 'alliance_id': alliance['id']}
            while len(requests) > 200:
                del requests[next(iter(requests))]
            finished = sorted((o for o in self.data['alliance_operations'].values() if o['alliance_id'] == alliance['id'] and o['status'] not in ACTIVE), key=lambda o: o['created_at'], reverse=True)
            for old in finished[50:]:
                del self.data['alliance_operations'][old['id']]
            self._touch_player_activity(player_id)
            return response

    def _operation_return(self, f, *, early=False):
        if f['status'] == 'returning':
            return
        seconds = f.get('return_seconds', f['seconds'])
        if early:
            duration = max(1, f['arrives_at'] - f['started_at'])
            # Presentation metadata only: preserve the actual turnaround point.
            f['map_return_fraction'] = max(0., min(1., (self.now - f['started_at']) / duration))
            seconds = min(seconds, max(1, self.now - f['started_at']))
        f['seconds'] = seconds
        self._return(f)

    def _operation_cancel(self, op):
        if op['status'] not in ACTIVE:
            return
        op['status'] = 'cancelled'
        op['finished_at'] = self.now
        for item in op['participants'].values():
            f = self.data['fleets'].get(item['fleet_id'])
            if f:
                self._operation_return(f, early=True)
            item['status'] = 'returning'

    def _alliance_deadlines(self):
        return [o['impact_at'] for o in self.data.get('alliance_operations', {}).values() if o['status'] in ACTIVE]

    def _advance_alliance_operations(self):
        # Defense arrivals and expiry precede attacks at the same timestamp.
        for fleet in list(self.data['fleets'].values()):
            if fleet['mission'] == 'alliance_defense' and fleet['status'] != 'returning' and fleet['arrives_at'] <= self.now:
                self._alliance_complete_fleet(fleet)
        for op in sorted(self.data.get('alliance_operations', {}).values(), key=lambda o: (o['impact_at'], o['id'])):
            if op['status'] not in ACTIVE or op['impact_at'] > self.now:
                continue
            target = self.data['planets'].get(op['target']['id'])
            attack = []
            for owner, item in op['participants'].items():
                f = self.data['fleets'].get(item['fleet_id'])
                membership = self._alliance_for(owner) if owner in self.data['players'] else None
                valid = (f and f['status'] == 'outbound' and membership and membership['id'] == op['alliance_id']
                         and target and target['owner_id'] == op['target_owner_id'] and self._operation_target_allowed(owner, target))
                if valid:
                    attack.append(f)
                elif f:
                    self._operation_return(f, early=True)
            if not attack:
                self._operation_cancel(op)
                continue
            # A resolving state is never externally committed: World's enclosing
            # transaction atomically persists combat, reports and fleet returns.
            op['status'] = 'resolving'
            op['result'] = self._alliance_battle(attack, target)
            op['status'] = 'completed'
            op['finished_at'] = self.now
            for item in op['participants'].values():
                f = self.data['fleets'].get(item['fleet_id'])
                item['ships'] = dict(f['ships']) if f else dict.fromkeys(item['ships'], 0)
                item['status'] = 'returning' if f else 'destroyed'

    def _alliance_supports_at(self, target):
        supports = []
        for f in self.data['fleets'].values():
            if (f['mission'] != 'alliance_defense' or f['target_id'] != target['id']
                    or f['status'] == 'returning' or f.get('hold_until', 0) <= self.now
                    or f.get('support_owner_id') != target['owner_id']
                    or not self._allied(f['owner_id'], target['owner_id'])):
                continue
            if f['status'] == 'holding' or f['arrives_at'] <= self.now:
                supports.append(f)
        return sorted(supports, key=lambda f: f['id'])

    def _alliance_has_support(self, target):
        return bool(self._alliance_supports_at(target))

    def _alliance_complete_fleet(self, f):
        if f['mission'] not in ('alliance_attack', 'alliance_defense') or f['status'] == 'returning':
            return False
        if f['id'] not in self.data['fleets']:
            return True
        if f['mission'] == 'alliance_attack':
            self._advance_alliance_operations()
            if f['id'] in self.data['fleets'] and f['status'] != 'returning':
                self._operation_return(f)
            return True
        target = self.data['planets'].get(f['target_id'])
        if (not target or target['owner_id'] != f.get('support_owner_id')
                or not self._allied(f['owner_id'], target['owner_id']) or f['hold_until'] <= self.now):
            self._operation_return(f)
        else:
            f.update(status='holding', started_at=self.now, arrives_at=f['hold_until'],
                     seconds=f['hold_until'] - self.now)
        return True

    def _alliance_member_departed(self, player_id, alliance_id):
        for op in self.data.get('alliance_operations', {}).values():
            if op['alliance_id'] != alliance_id or op['status'] not in ACTIVE:
                continue
            if op['creator_id'] == player_id:
                self._operation_cancel(op)
            elif player_id in op['participants']:
                f = self.data['fleets'].get(op['participants'][player_id]['fleet_id'])
                if f:
                    self._operation_return(f, early=True)
                del op['participants'][player_id]
                if not op['participants']:
                    self._operation_cancel(op)
        for f in list(self.data['fleets'].values()):
            if (f['mission'] == 'alliance_defense' and f['status'] != 'returning'
                    and (f['owner_id'] == player_id or f.get('support_owner_id') == player_id)):
                self._operation_return(f, early=f['status'] == 'outbound')

    def _alliance_member_joined(self, player_id, alliance_id):
        # Joining never permits friendly attacks already in flight to proceed.
        for f in list(self.data['fleets'].values()):
            if f['mission'] not in ('attack', 'alliance_attack') or f['status'] != 'outbound':
                continue
            target = self.data['planets'].get(f['target_id'])
            if target and self._allied(f['owner_id'], target['owner_id']):
                self._operation_return(f, early=True)
                op = self.data.get('alliance_operations', {}).get(f.get('operation_id'))
                if op:
                    op['participants'].pop(f['owner_id'], None)
                    if not op['participants']:
                        self._operation_cancel(op)

    def _coalition_formation(self, owner, ships, formation_id, *, fleet=None, target=None):
        static = self._specs(owner, 'defenses') if target else {}
        specs = {**self._specs(owner, 'ships'), **static}
        rules = self._rules(owner)
        effects = self._building_effects(target) if target else (fleet or {}).get('building_effects', {})
        weapons = (self._swarm_weapon_level(target) if target else (fleet or {}).get('swarm_weapon_level', 0)) if owner == 'khar' else self._player(owner)['research']['weapons']
        return {'id': formation_id, 'owner': owner, 'ships': ships, 'before': dict(ships),
                'fleet': fleet, 'specs': specs, 'static': static, 'rules': rules, 'effects': effects,
                'weapons': weapons, 'wounds': {}, 'native': target is not None,
                'type_traits': {**self._ship_traits(owner), **defenses.TRAITS},
                'regeneration': self._regeneration_fraction(rules, defense_effects=effects if target else None)}

    def _coalition_side(self, formations):
        result = {'name': '', 'race': '', 'units': [], 'initial': {}, 'participants': []}
        names, races = [], set()
        for form in formations:
            side = battle_replay.side(self, form['owner'], form['ships'], form['specs'], form['static'])
            name = self.data['players'].get(form['owner'], {}).get('name', '')
            if form['owner'] == 'khar':
                name = t('Rój Khar')
            names.append(str(name))
            races.add(side['race'])
            result['participants'].append({'owner_id': form['owner'], 'owner_name': str(name),
                                          'race': side['race'], 'formation_id': form['id']})
            for unit in side['units']:
                key = unit['key']
                unit.update(key=form['id'] + ':' + key, unit_key=key, formation_id=form['id'],
                            owner_id=form['owner'], owner_name=str(name), race=side['race'])
                unit['name_i18n'] = store_text(t('{0} · {1}').format(name, form['specs'][key][0]))
                unit['unit_name_i18n'] = store_text(form['specs'][key][0])
                result['units'].append(unit)
                result['initial'][unit['key']] = side['initial'][key]
        result['name'] = ', '.join(names)
        result['race'] = next(iter(races)) if len(races) == 1 else 'mixed'
        return result

    @staticmethod
    def _coalition_positions(formations, initial):
        result = {}
        for form in formations:
            for k in form['ships']:
                key = form['id'] + ':' + k
                if key in initial:
                    result[key] = {'count': int(form['ships'][k]), 'wounds': float(form['wounds'].get(k, 0))}
        return result

    def _coalition_power(self, form, round_no, enemy_swarm=False, *, combat_only=False, assault=False):
        multiplier = form['rules']['first_volley_multiplier'] if round_no == 1 else 1.0
        if form['native'] and round_no == 1:
            multiplier *= 1 + form['effects'].get('defense_first_volley', 0)
        if enemy_swarm:
            multiplier *= 1 + self._bonuses(form['owner']).get('swarm_damage', 0)
        factors = defenses.round_factors(round_no) if form['native'] else {}
        if enemy_swarm and assault:
            factors = {**factors, **{k: x.get('swarm_attack_multiplier', 1) for k, x in SHIP_TRAITS.items()}}
        factors.update(self._ship_round_factors(form['owner'], round_no))
        ships = {k: n for k, n in form['ships'].items() if not combat_only or k in COMBAT_SHIPS}
        return self._power(ships, form['weapons'], form['specs'], multiplier,
                           type_multipliers=factors, owner_id=form['owner'])

    def _coalition_damage(self, forms, damage, events):
        effective = {}
        for f in forms:
            resistance = max(.05, 1 - f['rules']['damage_reduction'])
            effective[f['id']] = sum(max(0, n * f['specs'][k][5] - f['wounds'].get(k, 0)) /
                (resistance * (1 - min(.95, max(0, f['type_traits'].get(k, {}).get('damage_reduction', 0)))))
                for k, n in f['ships'].items() if n)
        total = sum(effective.values())
        if total <= 0:
            return
        for f in forms:
            if effective[f['id']] <= 0:
                continue
            local = []
            self._damage(f['ships'], damage * effective[f['id']] / total, f['wounds'], f['specs'],
                         f['rules']['damage_reduction'],
                         {k: v.get('damage_reduction', 0) for k, v in f['type_traits'].items()}, events=local)
            for event in local:
                event['key'] = f['id'] + ':' + event['key']
            events.extend(local)

    def _coalition_regenerate(self, forms, events):
        for f in forms:
            local = []
            self._regenerate(f['ships'], f['wounds'], f['regeneration'],
                             {k: v.get('regeneration_fraction', 0) for k, v in f['type_traits'].items()}, events=local)
            for event in local:
                event['key'] = f['id'] + ':' + event['key']
            events.extend(local)

    def _alliance_battle(self, attack_fleets, target):
        """Resolve all formations once; caller already validates diplomacy/target.

        Support fleets stay separate from host ships and never receive host
        buildings, weapons or race bonuses. Their paid holding timer continues.
        """
        attack_fleets = sorted(attack_fleets, key=lambda f: f['id'])
        attackers = [self._coalition_formation(f['owner_id'], f['ships'], f['id'], fleet=f) for f in attack_fleets]
        host = self._coalition_formation(target['owner_id'], {**target['ships'], **target.get('defenses', {})},
                                         'planet_' + target['id'], target=target)
        supporters = self._alliance_supports_at(target)
        defenders = [host] + [self._coalition_formation(f['owner_id'], f['ships'], f['id'], fleet=f) for f in supporters]
        defender = target['owner_id']
        rare_eligible = (defender == 'khar' and (host['before'].get('frigate', 0) + host['before'].get('cruiser', 0)
                        + sum(target.get('defenses', {}).values())) > 0
                        and (not target.get('swarm_loot_sealed', False) or self._swarm_ready(target)))
        attacking_swarm = all(f['owner'] == 'khar' for f in attackers)
        contributions = {f['id']: self._coalition_power(f, 1, defender == 'khar', combat_only=True, assault=True) for f in attackers}
        replay = {'schema': 1, 'at': self.now,
                  'planet': {'name': target['name'], 'art_key': 'worlds/planet_' + target.get('environment', {}).get('type', 'crater')},
                  'attacker': self._coalition_side(attackers), 'defender': self._coalition_side(defenders),
                  'rounds': [], 'damage_rule': 'proportional_effective_hull'}
        def positions():
            return {side: self._coalition_positions(forms, replay[side]['initial'])
                    for side, forms in (('attacker', attackers), ('defender', defenders))}
        for round_no in range(1, 7):
            if not sum(sum(f['ships'].values()) for f in attackers) or not sum(sum(f['ships'].values()) for f in defenders):
                break
            recorded = {'number': round_no, 'before': positions(), 'hits': {'attacker': [], 'defender': []},
                        'heals': {'attacker': [], 'defender': []}}
            powers_a = {f['id']: self._coalition_power(f, round_no, defender == 'khar', assault=True) for f in attackers}
            powers_d = {f['id']: self._coalition_power(f, round_no, attacking_swarm) for f in defenders}
            recorded['formation_salvos'] = {'attacker': powers_a, 'defender': powers_d}
            recorded['salvos'] = {'attacker': sum(powers_a.values()), 'defender': sum(powers_d.values())}
            self._coalition_damage(defenders, sum(powers_a.values()), recorded['hits']['defender'])
            self._coalition_damage(attackers, sum(powers_d.values()), recorded['hits']['attacker'])
            recorded['after_damage'] = positions()
            self._coalition_regenerate(attackers, recorded['heals']['attacker'])
            self._coalition_regenerate(defenders, recorded['heals']['defender'])
            recorded['after'] = positions()
            replay['rounds'].append(recorded)
        target['ships'] = {k: host['ships'].get(k, 0) for k in self._specs(defender, 'ships')}
        target['defenses'] = {k: host['ships'].get(k, 0) for k in host['static']}
        victory = not sum(sum(f['ships'].values()) for f in defenders) and sum(sum(f['ships'].values()) for f in attackers) > 0
        free = {f['id']: capacity(f['specs'], f['ships']) for f in attackers}
        recovered = dict.fromkeys(free, 0)
        for f in attack_fleets:
            f['cargo'] = dict.fromkeys(RESOURCES, 0)
            f['swarm_crystals'] = 0
            f['swarm_destruction_bonus'] = 0
        if victory:
            contribution_sum = sum(contributions.values())
            if defender == 'khar':
                # The quota is weighted once, never multiplied by members.
                weighted_bonus = (sum(contributions[f['id']] * self._bonuses(f['owner']).get('swarm_loot', 0)
                                      for f in attackers) / contribution_sum) if contribution_sum else 0
                quota = math.floor(swarm.RAID_CRYSTALS[swarm.kind(target)] * (1 + weighted_bonus))
                crystals = min(int(target.get('swarm_crystals', 0)), quota, sum(free.values())) if rare_eligible else 0
                shares = apportion(crystals, contributions, free)
                for f in attack_fleets:
                    f['swarm_crystals'] = shares[f['id']]
                    free[f['id']] -= shares[f['id']]
                target['swarm_crystals'] = max(0, target.get('swarm_crystals', 0) - sum(shares.values()))
                # One fixed outpost reward for the whole engagement, after real
                # crystal stock and before ordinary cargo, limited by survivors.
                if swarm.kind(target) != 'hive':
                    bonus = min(swarm.DESTRUCTION_CRYSTALS, sum(free.values()))
                    shares = apportion(bonus, contributions, free)
                    for f in attack_fleets:
                        f['swarm_destruction_bonus'] = shares[f['id']]
                        f['swarm_crystals'] += shares[f['id']]
                        free[f['id']] -= shares[f['id']]
                target['swarm_loot_sealed'] = True
                target['swarm_suppressed_until'] = 0
            destroyed_metal = sum(self._unit_construction_cost(f['owner'], k, f['specs'][k], stationary=k in f['static'])['metal']
                                  * (n - f['ships'].get(k, 0))
                                  for f in defenders for k, n in f['before'].items() if n)
            for f in attackers:
                share = contributions[f['id']] / contribution_sum if contribution_sum else 0
                fraction = max(0, min(1, f['effects'].get('wreck_recovery_fraction', 0)))
                n = min(free[f['id']], math.floor(round(destroyed_metal * share * fraction, 6)))
                f['fleet']['cargo']['metal'] = n
                free[f['id']] -= n
                recovered[f['id']] = n
            available = self._lootable_resources(target)
            loot = apportion(min(sum(available.values()), sum(free.values())), available, available)
            for resource in RESOURCES:
                shares = apportion(loot[resource], free, free)
                target['resources'][resource] -= sum(shares.values())
                for f in attack_fleets:
                    f['cargo'][resource] += shares[f['id']]
                    free[f['id']] -= shares[f['id']]
        eradicated = (victory and defender == 'khar' and self._eradicate_swarm_nest(
            target, observers=[f['owner'] for f in attackers]))
        replay['final'] = positions()
        replay['outcome'] = 'attacker_wins' if victory else 'attacker_destroyed' if not sum(sum(f['ships'].values()) for f in attackers) else 'retreat'
        replay['swarm_eradicated'] = bool(eradicated)
        replay['cargo'] = {k: sum(f['cargo'][k] for f in attack_fleets) for k in RESOURCES}
        replay['swarm_crystals'] = sum(f['swarm_crystals'] for f in attack_fleets)
        replay['swarm_destruction_bonus'] = sum(f['swarm_destruction_bonus'] for f in attack_fleets)
        replay['participant_results'] = []
        for side, forms in (('attacker', attackers), ('defender', defenders)):
            replay[side]['losses'] = {key: before['count'] - replay['final'][side][key]['count'] for key, before in replay[side]['initial'].items()}
            for f in forms:
                fleet = f['fleet'] or {}
                participant = next(x for x in replay[side]['participants'] if x['formation_id'] == f['id'])
                replay['participant_results'].append({**participant, 'side': side, 'initial': dict(f['before']),
                    'survivors': dict(f['ships']), 'losses': {k: n - f['ships'].get(k, 0) for k, n in f['before'].items() if n},
                    'cargo': dict(fleet.get('cargo', dict.fromkeys(RESOURCES, 0))) if side == 'attacker' else dict.fromkeys(RESOURCES, 0),
                    'swarm_crystals': fleet.get('swarm_crystals', 0) if side == 'attacker' else 0,
                    'swarm_destruction_bonus': fleet.get('swarm_destruction_bonus', 0) if side == 'attacker' else 0,
                    'recovered_metal': recovered.get(f['id'], 0)})
        outcome = t('Zwycięstwo atakujących') if victory else t('Atak odparty') if replay['outcome'] == 'attacker_destroyed' else t('Nierozstrzygnięta bitwa — odwrót')
        for participant in replay['participant_results']:
            owner = participant['owner_id']
            if owner not in self.data['players']:
                continue
            own_side = participant['side']
            lost = sum(participant['losses'].values())
            left = sum(participant['survivors'].values())
            cargo = participant['cargo']
            summary = t('{0}: {1}. Rundy: {2}. Twoje straty: {3}; ocalałe jednostki: {4}.').format(target['name'], outcome, len(replay['rounds']), lost, left)
            if own_side == 'attacker':
                summary += ' ' + t('Twoja zdobycz: metal {0}, kryształy {1}, paliwo {2}; Kryształy Roju: {3}. Ładunek otrzymasz po powrocie.').format(cargo['metal'], cargo['crystal'], cargo['fuel'], participant['swarm_crystals'])
                if eradicated:
                    summary += t(' Gniazdo Roju zostało zniszczone. Planeta jest wolna i można ją skolonizować.')
                    if participant['swarm_destruction_bonus']:
                        summary += t(' Premia za zniszczenie gniazda: {0} Kryształów Roju (wliczona w ładunek).').format(participant['swarm_destruction_bonus'])
                elif victory and defender == 'khar':
                    summary += t(' Główny ul przetrwał. Zachowuje budynki i odbudowuje flotę z własnych zasobów; planety nie można skolonizować.')
            elif participant['formation_id'] != host['id']:
                summary += ' ' + t('Ocalałe wsparcie pozostaje na dyżurze i wróci do kolonii swojego właściciela.')
            summary += ' ' + t('Obrażenia dzielą się proporcjonalnie do wytrzymałości flot; w każdej flocie najpierw trafiane są słabsze kadłuby.')
            self._report(owner, t('Raport wspólnej bitwy'), summary, 'swarm/weapon' if defender == 'khar' or attacking_swarm else '', participant['swarm_crystals'], replay=replay)
        for f in supporters:
            if not sum(f['ships'].values()):
                self.data['fleets'].pop(f['id'], None)
        for f in attack_fleets:
            self._operation_return(f)
        return {'outcome': replay['outcome'], 'rounds': len(replay['rounds']),
                'cargo': dict(replay['cargo']), 'swarm_crystals': replay['swarm_crystals'],
                'swarm_eradicated': bool(eradicated),
                'swarm_destruction_bonus': replay['swarm_destruction_bonus'],
                'participants': copy.deepcopy(replay['participant_results'])}

