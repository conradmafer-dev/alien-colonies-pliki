"""Server-filtered fog of war: local live sensors and immutable scout records."""
from __future__ import annotations
import copy

try:
    from . import planetary
    from .i18n import t
    from .races import RACES, UNIQUE_BUILDINGS
except ImportError:
    import planetary
    from i18n import t
    from races import RACES, UNIQUE_BUILDINGS


def ranges(level):
    level = max(0, min(12, level))
    return {'level': level, 'range': (level + 1) // 2 if level else -1,
            'building_range': (level - 6) // 2 if level >= 6 else -1}


class ObservationMixin:
    def _observation_coverage(self, player_id):
        coverage = {}
        navigation = self._galaxy_navigation()
        for planet in self.data['planets'].values():
            if planet['owner_id'] != player_id:
                continue
            sight = ranges(planet['buildings'].get('observatory', 0))
            if sight['range'] < 0:
                continue
            for system_id, distance in navigation.hop_distances(planet['system_id']).items():
                tier = 2 if distance <= sight['building_range'] else 1 if distance <= sight['range'] else 0
                coverage[system_id] = max(coverage.get(system_id, 0), tier)
        return coverage

    def _planet_identity(self, planet, *, trait_known=False, basic=False):
        item = {k: planet[k] for k in ('id', 'name', 'system_id', 'slot', 'owner_type', 'owner_id', 'galaxy_id')}
        owner = planet['owner_id']
        item['is_home_planet'] = (planet['owner_type'] == 'player'
                                  and self._player(owner)['home_id'] == planet['id'])
        item['owner_name'] = '' if not owner else 'Rój Khar' if owner == 'khar' else self._player(owner)['name']
        race = self._race_id(owner)
        item.update(race_id='swarm' if owner == 'khar' else race,
                    race_name='Rój Khar' if owner == 'khar' else RACES[race]['name'] if race else '',
                    environment=copy.deepcopy(planet.get('environment', {})))
        if planet['owner_type'] == 'player':
            alliance = self._alliance_for(owner)
            if alliance:
                item.update(alliance_id=alliance['id'], alliance_tag=alliance['tag'], alliance_name=alliance['name'])
            item['protected_until'] = self._player(owner)['protected_until']
        if trait_known and 'rare_trait' in planet:
            item['rare_trait'] = planet['rare_trait']
        if basic:
            item['environment'] = {'type': planet['environment']['type']}
        return item

    def _remember_trait(self, player_id, planet, source):
        if not planet.get('environment') or 'rare_trait' not in planet:
            return
        records = self._player(player_id).setdefault('trait_intel', {})
        previous = records.get(planet['id'], {})
        records[planet['id']] = {
            'discovered_at': previous.get('discovered_at', self.now),
            'observed_at': self.now, 'source': source,
            'identity': self._planet_identity(planet, trait_known=True, basic=True)}

    def _refresh_trait_intel(self):
        # Called inside the save transaction, including observatory completions.
        for player_id in self.data['players']:
            coverage = self._observation_coverage(player_id)
            for planet in self.data['planets'].values():
                if planet['owner_id'] == player_id:
                    self._remember_trait(player_id, planet, 'colony')
                elif coverage.get(planet['system_id'], 0):
                    self._remember_trait(player_id, planet, 'observatory')

    def _render_identity(self, identity):
        item = copy.deepcopy(identity)
        # Compute from the visible identity, not the hidden current owner. A
        # dated scout snapshot must not become a live intelligence side channel.
        item['is_protected'] = (item.get('owner_type') == 'player'
                                and item.get('protected_until', 0) > self.now)
        item.pop('rare_trait', None)
        item['environment'] = planetary.public_environment(identity)
        environment = item['environment']
        item['planet_art'] = environment.get('planet_art', '')
        item['colony_art'] = environment.get('colony_art', '')
        item['race_name'] = t(item.get('race_name', ''))
        if item.get('owner_id') == 'khar':
            item['owner_name'] = t('Rój Khar')
        return item

    def _building_observation(self, planet):
        specs = self._specs(planet['owner_id'], 'buildings')
        race = self._race_id(planet['owner_id'])
        foreign = {key: meta['spec'] for race_id, buildings in UNIQUE_BUILDINGS.items()
                   if race_id != race for key, meta in buildings.items()}
        return [{'key': key, 'name': t(spec[0]), 'level': planet['buildings'].get(key, 0),
                 'inactive': key in foreign}
                for key, spec in {**foreign, **specs}.items()
                if planet['buildings'].get(key, 0) > 0]

    def _capture_system_intel(self, player_id, planet):
        """One completed scan refreshes every planet's occupancy, never wallets."""
        if player_id not in self.data['players']:
            return None
        player = self._player(player_id)
        system = next(s for s in self.data['systems'] if s['id'] == planet['system_id'])
        identities = [self._planet_identity(self.data['planets'][pid]) for pid in system['planet_ids']]
        counts = {'own': 0, 'player': 0, 'alien': 0, 'empty': 0}
        for identity in identities:
            category = 'own' if identity['owner_id'] == player_id else identity['owner_type']
            counts[category] += 1
        snapshot = {'system_id': system['id'], 'system_name': system['name'], 'galaxy_id': system['galaxy_id'],
                    'scouted_at': self.now, 'planets_count': len(identities), 'counts': counts, 'planets': identities}
        player.setdefault('system_intel', {})[system['id']] = copy.deepcopy(snapshot)
        return snapshot

    def _render_system_scout(self, snapshot):
        return {key: copy.deepcopy(snapshot[key]) for key in
                ('system_id', 'system_name', 'galaxy_id', 'scouted_at', 'planets_count', 'counts')} | {
                    'planets': [{**self._render_identity(identity), 'scouted_at': snapshot['scouted_at']}
                                for identity in snapshot['planets']]}

    def _complete_system_scout(self, fleet, target):
        snapshot = self._capture_system_intel(fleet['owner_id'], target)
        if snapshot is None:
            return
        counts = snapshot['counts']
        summary = t('{0}: planety {1}. Twoje: {2}, inni gracze: {3}, Rój: {4}, wolne: {5}.').format(
            snapshot['system_name'], snapshot['planets_count'], counts['own'], counts['player'], counts['alien'], counts['empty'])
        summary += ' ' + t('Zwiad odświeżył właścicieli wszystkich planet w układzie. Zbadaj wybraną planetę, aby poznać jej zasoby, flotę i obronę.')
        self._report(fleet['owner_id'], t('Raport zwiadu układu'), summary)
        self._player(fleet['owner_id'])['reports'][0]['system_snapshot'] = copy.deepcopy(snapshot)

    def _capture_planetary_intel(self, player_id, planet):
        if player_id not in self.data['players']:
            return
        player = self._player(player_id)
        self._remember_trait(player_id, planet, 'scout')
        self._capture_system_intel(player_id, planet)
        player.setdefault('planet_intel', {})[planet['id']] = {
            'scouted_at': self.now, 'identity': self._planet_identity(planet, trait_known=True),
            'buildings': copy.deepcopy(planet['buildings']), 'resources': copy.deepcopy(planet['resources']),
            'ships': copy.deepcopy(planet['ships']), 'defenses': copy.deepcopy(planet.get('defenses', {}))}

    def _render_planet_scout(self, snapshot):
        result = self._render_identity(snapshot['identity'])
        result.update(scouted_at=snapshot['scouted_at'], resources={k: int(v) for k, v in snapshot['resources'].items()},
                      ships=copy.deepcopy(snapshot['ships']), defenses=copy.deepcopy(snapshot['defenses']))
        # Freeze race identity as well as levels; account deletion must not turn
        # an old alien laboratory into a human building in a previous report.
        race = snapshot['identity'].get('race_id', '')
        if race == 'swarm':
            try:
                from .swarm import BUILDINGS
            except ImportError:
                from swarm import BUILDINGS
            specs = BUILDINGS
        else:
            specs = {**(RACES[race]['buildings'] if race in RACES else self._specs('', 'buildings')),
                     **{k: v['spec'] for k, v in UNIQUE_BUILDINGS.get(race, {}).items()},
                     'observatory': planetary.OBSERVATORY_SPEC}
        foreign = {key: meta['spec'] for race_id, buildings in UNIQUE_BUILDINGS.items()
                   if race_id != race for key, meta in buildings.items()}
        specs = {**foreign, **specs}
        try:
            from . import defenses, swarm
        except ImportError:
            import defenses, swarm
        ship_specs = swarm.SHIPS if race == 'swarm' else RACES[race]['ships'] if race in RACES else self._specs('', 'ships')
        defense_specs = defenses.specs_for(race)
        for section, unit_specs in (('ships', ship_specs), ('defenses', defense_specs)):
            result[section + '_display'] = [{'key': k, 'name': t(unit_specs[k][0]) if k in unit_specs else k, 'count': n}
                                           for k, n in snapshot[section].items() if n > 0]
        result['observed_buildings'] = [{'key': k, 'name': t(specs[k][0]) if k in specs else k,
                                        'level': v, 'inactive': k in foreign}
                                        for k, v in snapshot['buildings'].items() if v > 0]
        return result

    def _known_planet(self, player_id, planet, coverage=None):
        if planet['owner_id'] == player_id or planet['id'] in self._player(player_id).get('trait_intel', {}):
            return True
        coverage = self._observation_coverage(player_id) if coverage is None else coverage
        if coverage.get(planet['system_id'], 0):
            return True
        record = self._player(player_id).get('system_intel', {}).get(planet['system_id'], {})
        return any(p['id'] == planet['id'] for p in record.get('planets', []))

    def _public_observation_map(self, player_id):
        coverage = self._observation_coverage(player_id)
        navigation = self._galaxy_navigation()
        player = self._player(player_id)
        galaxy, own = [], []
        for system in self.data['systems']:
            tier = coverage.get(system['id'], 0)
            record = player.get('system_intel', {}).get(system['id'], {})
            identities = {q['id']: q for q in record.get('planets', [])}
            memories = {pid: player.get('trait_intel', {}).get(pid, {}) for pid in system['planet_ids']}
            observed_at = max((m.get('observed_at', 0) for m in memories.values()), default=0)
            remembered = observed_at > record.get('scouted_at', 0) and any(
                m and m.get('source') != 'colony' for m in memories.values())
            view = {k: system[k] for k in ('id', 'x', 'y', 'galaxy_id')}
            view.update(navigation.public_fields(system['id']))
            # A stable physical arrival point supports a repeat scan even when
            # every planet was previously known. It conveys no owner/count data.
            if system['planet_ids']:
                view['system_scout_target_id'] = system['planet_ids'][0]
            view.update(name=system['name'] if tier or record or observed_at else t('Nieznany układ {0}').format(system['id'][1:]),
                        visibility='observed' if tier else 'remembered' if remembered else 'scouted' if record else 'unknown',
                        scouted_at=record.get('scouted_at', 0), observed_at=observed_at, planets=[])
            for pid in system['planet_ids']:
                planet = self.data['planets'][pid]
                owned = planet['owner_id'] == player_id
                memory = memories[pid]
                if not (tier or owned or pid in identities or memory):
                    continue
                remembered_planet = bool(memory and memory['observed_at'] > record.get('scouted_at', 0))
                if tier or owned:
                    identity = self._planet_identity(planet, trait_known=True)
                else:
                    identity = copy.deepcopy(memory['identity'] if remembered_planet or pid not in identities else identities[pid])
                    if memory:
                        # Terrain and traits are immutable; owners remain dated.
                        old_environment = identities.get(pid, {}).get('environment', {})
                        identity['environment'] = {**old_environment, **identity['environment']}
                        identity['rare_trait'] = memory['identity']['rare_trait']
                item = self._render_identity(identity)
                if tier == 1 and not owned and pid not in identities:
                    item['environment'] = {k: v for k, v in item['environment'].items() if k in ('type', 'type_name', 'planet_art', 'colony_art', 'trait')}
                item.update(visibility='own' if owned else 'observed' if tier else 'remembered' if remembered_planet or pid not in identities else 'scouted',
                            scouted_at=record.get('scouted_at', 0), observed_at=memory.get('observed_at', 0))
                if owned or tier >= 2:
                    item['observed_buildings'] = self._building_observation(planet)
                    item['building_visibility'] = 'live'
                snapshot = player.get('planet_intel', {}).get(pid)
                if snapshot:
                    item['planet_scout'] = self._render_planet_scout(snapshot)
                if item.get('owner_id') == 'khar':
                    item['has_scout'] = False
                    legacy = player.get('scout_intel', {}).get(pid)
                    if legacy:
                        item.update(self._render_swarm_intel(legacy))
                        # Recon art must not override the physical biome.
                        item['planet_art'] = item['environment'].get('planet_art', '')
                        item['colony_art'] = item['environment'].get('colony_art', '')
                view['planets'].append(item)
                if owned:
                    item['fields'] = planetary.fields(planet)
                    own.append(copy.deepcopy(item))
                    if view['visibility'] == 'unknown':
                        view['visibility'], view['name'] = 'colony', system['name']
            # A radio bearing is enough to send an exploratory scout, but never
            # discloses the number, owners, environments or buildings of planets.
            unknown = [pid for pid in system['planet_ids'] if pid not in {q['id'] for q in view['planets']}]
            if unknown:
                view['scout_target_id'] = unknown[0]
            galaxy.append(view)
        return galaxy, own

    def _observation_state(self, player_id, planet):
        profile = ranges(planet['buildings'].get('observatory', 0))
        profile.update(schema=1, galaxy_id=planet['galaxy_id'], system_id=planet['system_id'],
                       next=ranges(min(12, profile['level']+1)),
                       sources=[{'planet_id': p['id'], 'name': p['name'], 'galaxy_id': p['galaxy_id'],
                                 'system_id': p['system_id'], **ranges(p['buildings'].get('observatory', 0))}
                                for p in self.data['planets'].values() if p['owner_id'] == player_id and p['buildings'].get('observatory', 0)])
        return profile

    def _ensure_observation(self):
        if self.data.get('observation_schema', 0) >= 1:
            return
        for player in self.data['players'].values():
            player.setdefault('system_intel', {})
            player.setdefault('planet_intel', {})
            # Preserve only genuinely recorded historical observations. Do not
            # upgrade an old scout into knowledge of unvisited neighbouring planets.
            for pid, old in player.get('scout_intel', {}).items():
                planet = self.data['planets'].get(pid)
                if not planet or not old.get('scouted_at'):
                    continue
                identity = {k: old.get(k, planet[k]) for k in ('id', 'name', 'system_id', 'slot', 'galaxy_id')}
                identity.update(owner_type=old.get('owner_type', 'alien'), owner_id=old.get('owner_id', 'khar'),
                                owner_name='Rój Khar', race_id='swarm', race_name='Rój Khar',
                                environment=copy.deepcopy(planet['environment']))
                record = player['system_intel'].setdefault(planet['system_id'], {'scouted_at': old['scouted_at'], 'planets': []})
                record['planets'].append(identity)
                record['scouted_at'] = max(record['scouted_at'], old['scouted_at'])
                player['planet_intel'].setdefault(pid, {'identity': identity, 'scouted_at': old['scouted_at'],
                    **{k: copy.deepcopy(old.get(k, {})) for k in ('buildings', 'resources', 'ships', 'defenses')}})
        self.data['observation_schema'] = 1

    def _observation_onboarding(self, guide, galaxy, origin):
        bearing = next((s.get('scout_target_id') for s in galaxy if s['galaxy_id'] == origin['galaxy_id'] and s.get('scout_target_id')), '')
        for step in guide.get('steps', []):
            if step.get('action') == 'scout' and not step.get('target_id') and not step.get('done'):
                step['target_id'] = bearing
                step['description'] = t('Zbadaj nieznane układy, aby znaleźć Rój. Obserwatorium zapewni stały podgląd okolicy.')
            if step.get('action') in ('hunt', 'colonize') and not step.get('target_id') and not step.get('done'):
                step['description'] = t('Odkryj odpowiednią planetę zwiadem albo obserwatorium.')
        if guide.get('current') is not None:
            guide['current'] = next((dict(s) for s in guide.get('steps', []) if not s['done']), None)

