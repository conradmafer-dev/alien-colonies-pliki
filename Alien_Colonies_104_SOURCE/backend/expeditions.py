"""Restart-safe expeditions: rewards are frozen at departure and delivered on landing.

The stored target is a real planet for legacy fleet/account references. Only the
owner's public view uses a virtual expedition sector. No client supplies a roll.
"""
from __future__ import annotations
import copy
import hashlib
import math
import secrets
try:
    from .i18n import t
    from . import battle_replay, fleet_expansion
    from .races import SHIP_TRAITS
except ImportError:
    from i18n import t
    import battle_replay, fleet_expansion
    from races import SHIP_TRAITS

KEY = "expedition_base"
RESOURCES = ("metal", "crystal", "fuel")
HOURS = (1, 3, 6)
ART = "building_expedition_base"
SPEC = ("Baza ekspedycyjna", "Organizuje wyprawy po surowce i porzucone statki. Każdy poziom powyżej pierwszego zwiększa wartość znalezisk o 5%. Poziomy 6, 11, 16 i kolejne odblokowują dodatkową ekspedycję. Pokonanie patrolu Roju daje 25% szansy na Kryształ Roju, dostarczany po powrocie.", (4000, 6000, 2000), 1200)
OUTCOMES = ((50,"resources"),(10,"ships"),(20,"empty"),(10,"patrol"),(10,"delay"))

def profile(level):
    level=max(0,int(level))
    return {"level":level,"reward_bonus_percent":max(0,level-1)*5,
            "reward_multiplier":1+max(0,level-1)*.05,"slots":0 if not level else 1+(level-1)//5}

def roll(seed,label,maximum):
    return int.from_bytes(hashlib.sha256((seed+":"+label).encode()).digest(),"big") % maximum

def outcome(value):
    for chance,name in OUTCOMES:
        if value < chance:return name
        value-=chance
    raise ValueError("Invalid expedition roll")

def load_resources(budget,capacity):
    capacity=max(0,int(capacity));total=sum(budget.values())
    if total<=capacity:return dict(budget)
    result={k:int(capacity*budget[k]//total) for k in RESOURCES}
    remaining=capacity-sum(result.values())
    for k in sorted(RESOURCES,key=lambda k:(-(capacity*budget[k]%total),k))[:remaining]:result[k]+=1
    return result

class ExpeditionMixin:
    def _expedition_error(self,message,status=409):
        raise self.account_error_class(message,status)

    def _expedition_state(self,player_id,planet):
        levels=[int(p["buildings"].get(KEY,0)) for p in self.data["planets"].values() if p["owner_id"]==player_id and p["owner_type"]=="player"]
        highest=max(levels,default=0)
        active=sum(f["owner_id"]==player_id and f["mission"]=="expedition" for f in self.data["fleets"].values())
        zone={"id":"expedition:"+planet["system_id"],"name":str(t("Nieznany sektor")),"system_id":planet["system_id"],"galaxy_id":self._galaxy_id(planet)}
        return {"schema":1,**profile(planet["buildings"].get(KEY,0)),"highest_level":highest,
                "max_active":profile(highest)["slots"],"active":active,"hours":list(HOURS),"zone":zone,"patrol_crystal_chance_percent":25}

    def _expedition_quote(self,player_id,payload,require_affordable):
        origin=self._owned(player_id,payload.get("planet_id"));state=self._expedition_state(player_id,origin)
        if state["level"]<1:self._expedition_error(t("Zbuduj bazę ekspedycyjną na planecie startowej."))
        if state["active"]>=state["max_active"]:self._expedition_error(t("Wszystkie miejsca na ekspedycje są zajęte. Rozbuduj bazę albo poczekaj na powrót floty."))
        hours=payload.get("expedition_hours",1)
        if type(hours) is not int or hours not in HOURS:self._expedition_error(t("Wybierz 1, 3 albo 6 godzin poszukiwań."),400)
        if payload.get("target_id")!=state["zone"]["id"]:self._expedition_error(t("Wybierz strefę ekspedycyjną przy kolonii startowej."),400)
        if payload.get("travel_mode","normal")!="normal" or payload.get("scout_scope","planet")!="planet":self._expedition_error(t("Ekspedycja korzysta ze zwykłego lotu do pobliskiego sektora."),400)
        specs=self._specs(player_id,"ships")
        ships=self.expedition_counts(payload.get("ships"),specs,t("Liczba statków"),10000)
        cargo=self.expedition_counts(payload.get("cargo",{}),RESOURCES,t("Ładunek"),self.MAX_RESOURCE)
        if ships.get("scout",0)<1:self._expedition_error(t("Ekspedycja wymaga przynajmniej jednego zwiadowcy."))
        if any(n>origin["ships"].get(k,0) for k,n in ships.items()):self._expedition_error(t("Nie masz tylu statków na tej planecie."))
        if any(cargo.values()):self._expedition_error(t("Pozostaw ładownie ekspedycji wolne na znaleziska."),400)
        target={**origin,"slot":0,"name":state["zone"]["name"]}
        seconds,fuel=self._flight_numbers(origin,target,ships,self._player(player_id)["research"]["propulsion"])
        cost={"metal":0,"crystal":0,"fuel":fuel}
        if require_affordable and not self.expedition_affordable(origin,cost):self._expedition_error(t("Brakuje paliwa na ekspedycję."))
        return origin,target,ships,cargo,cost,seconds,fuel,self.expedition_capacity(specs,ships)

    def _expedition_preview(self,player_id,origin,payload,seconds):
        state=self._expedition_state(player_id,origin);hours=payload.get("expedition_hours",1);rates=self.production(origin)
        reward={k:min(self.MAX_RESOURCE,math.floor(rates[k]*hours*.5*state["reward_multiplier"])) for k in RESOURCES}
        return {"search_hours":hours,"search_seconds":hours*3600,"round_trip_seconds":2*seconds+hours*3600,
                "reward_budget":reward,"reward_bonus_percent":state["reward_bonus_percent"],"active":state["active"],
                "max_active":state["max_active"],"patrol_crystal_chance_percent":25,"zone":state["zone"]}

    def _prepare_expedition(self,player_id,origin,payload,seconds):
        allowed=[key for key in self._specs(player_id,"ships") if all(r["met"] for r in self._entry_requirements(player_id,origin,"ships",key))
                 and (self._race_id(player_id) or key not in ("interceptor","siege","freighter",*fleet_expansion.CAPITAL_ROLES))]
        return {**self._expedition_preview(player_id,origin,payload,seconds),"schema":1,"base_level":int(origin["buildings"].get(KEY,0)),
                "production_snapshot":dict(self.production(origin)),"flight_seconds":seconds,"allowed_ships":allowed,
                "seed":secrets.token_hex(32),"outcome":outcome(secrets.randbelow(100)),"resolved":False,"delayed":False}

    def _public_expedition_fleet(self,fleet,view):
        data=fleet["expedition"]
        view.update(target_id=data["zone"]["id"],target_name=data["zone"]["name"],
                    expedition={k:copy.deepcopy(data[k]) for k in ("search_hours","search_seconds","flight_seconds","reward_bonus_percent")},can_recall=fleet["status"]!="returning")
        view["expedition"]["phase"]=fleet["status"]
        if fleet["status"]=="exploring":view["expedition"]["search_until"]=fleet["arrives_at"]

    def _expedition_return(self,fleet,*,recalled=False):
        seconds=fleet["expedition"]["flight_seconds"]
        if recalled:
            if fleet["status"]=="returning":self._expedition_error(t("Ta flota już wraca."))
            if fleet["status"]=="outbound":
                elapsed=max(1,self.now-fleet["started_at"])
                fleet["map_return_fraction"]=min(1.,elapsed/max(1,fleet["seconds"]))
                seconds=min(seconds,elapsed)
            fleet["expedition"]["cancelled"]=True
        fleet["seconds"]=seconds
        self._return(fleet)

    def _expedition_found_ships(self,fleet):
        data=fleet["expedition"];owner=fleet["owner_id"];specs=self._specs(owner,"ships");budget=sum(data["reward_budget"].values());candidates=[]
        for key in data["allowed_ships"]:
            if key in specs:
                cost=sum(self._unit_construction_cost(owner,key,specs[key]).values())
                if 0<cost<=budget:candidates.append((key,cost))
        found={}
        for step in range(10):
            affordable=[(k,c) for k,c in candidates if c<=budget]
            if not affordable:break
            key,cost=affordable[roll(data["seed"],"ship:"+str(step),len(affordable))]
            found[key]=found.get(key,0)+1;fleet["ships"][key]=fleet["ships"].get(key,0)+1;budget-=cost
        return found

    def _expedition_patrol(self,fleet):
        """The ordinary six simultaneous rounds, racial salvos, traits and healing."""
        owner=fleet["owner_id"];data=fleet["expedition"];stage=1+max(0,data["base_level"]-1)//5
        defending={"scout":4*stage,"frigate":12*stage,"cruiser":stage};before=dict(fleet["ships"])
        specs_a,specs_d=self._specs(owner,"ships"),self._specs("khar","ships")
        rules_a,rules_d=self._rules(owner),self._rules("khar")
        traits_a,traits_d=self._ship_traits(owner),self._ship_traits("khar")
        wounds_a,wounds_d={},{}
        heals_a={k:v.get("regeneration_fraction",0) for k,v in traits_a.items()};heals_d={k:v.get("regeneration_fraction",0) for k,v in traits_d.items()}
        reductions_a={k:v.get("damage_reduction",0) for k,v in traits_a.items()};reductions_d={k:v.get("damage_reduction",0) for k,v in traits_d.items()}
        replay=battle_replay.start(self,owner,"khar",fleet["ships"],defending,specs_a,specs_d,{}, {"name":str(t("Patrol Roju"))})
        def positions():return {"attacker":battle_replay.snapshot(fleet["ships"],wounds_a,replay["attacker"]["initial"]),"defender":battle_replay.snapshot(defending,wounds_d,replay["defender"]["initial"])}
        for number in range(1,7):
            if not sum(fleet["ships"].values()) or not sum(defending.values()):break
            record={"number":number,"before":positions(),"hits":{"attacker":[],"defender":[]},"heals":{"attacker":[],"defender":[]}}
            siege={key:meta.get("swarm_attack_multiplier",1.) for key,meta in SHIP_TRAITS.items()}
            attack=self._power(fleet["ships"],self._player(owner)["research"]["weapons"],specs_a,
                               (rules_a["first_volley_multiplier"] if number==1 else 1.)*(1+self._bonuses(owner).get("swarm_damage",0)),
                               type_multipliers={**siege,**self._ship_round_factors(owner,number)},owner_id=owner)
            defense=self._power(defending,stage-1,specs_d,rules_d["first_volley_multiplier"] if number==1 else 1.,type_multipliers=self._ship_round_factors("khar",number),owner_id="khar")
            record["salvos"]={"attacker":attack,"defender":defense}
            self._damage(defending,attack,wounds_d,specs_d,rules_d["damage_reduction"],reductions_d,events=record["hits"]["defender"])
            self._damage(fleet["ships"],defense,wounds_a,specs_a,rules_a["damage_reduction"],reductions_a,events=record["hits"]["attacker"])
            record["after_damage"]=positions()
            self._regenerate(fleet["ships"],wounds_a,self._regeneration_fraction(rules_a),heals_a,events=record["heals"]["attacker"])
            self._regenerate(defending,wounds_d,self._regeneration_fraction(rules_d),heals_d,events=record["heals"]["defender"])
            record["after"]=positions();replay["rounds"].append(record)
        won=not sum(defending.values()) and sum(fleet["ships"].values())>0
        replay.update(final=positions(),outcome="attacker_wins" if won else "attacker_destroyed" if not sum(fleet["ships"].values()) else "retreat")
        replay["attacker"]["losses"]={k:n-fleet["ships"].get(k,0) for k,n in before.items() if n}
        replay["defender"]["losses"]={k:v["count"]-defending.get(k,0) for k,v in replay["defender"]["initial"].items()}
        return won,replay

    def _complete_expedition(self,fleet):
        if fleet["mission"]!="expedition" or fleet["status"]=="returning":return False
        data=fleet["expedition"]
        if fleet["status"]=="outbound":
            fleet.update(status="exploring",started_at=self.now,seconds=data["search_seconds"],arrives_at=self.now+data["search_seconds"]);return True
        if data["resolved"] or data.get("cancelled"):
            self._expedition_return(fleet);return True
        event=data["outcome"]
        if event=="delay" and not data["delayed"]:
            data["delayed"]=True;extra=data["search_seconds"]//2
            fleet.update(started_at=self.now,seconds=extra,arrives_at=self.now+extra)
            self._report(fleet["owner_id"],t("Opóźniona ekspedycja"),t("Problemy nawigacyjne wydłużyły poszukiwania o {0} godzin.").format(data["search_hours"]/2),ART,report_kind="expedition");return True
        data["resolved"]=True;specs=self._specs(fleet["owner_id"],"ships");capacity=self.expedition_capacity(specs,fleet["ships"])
        replay,found,won=None,{},False
        if event=="patrol":
            won,replay=self._expedition_patrol(fleet);capacity=self.expedition_capacity(specs,fleet["ships"])
            if won and capacity>=1 and roll(data["seed"],"crystal",100)<25:
                fleet["swarm_crystals"]=1;capacity-=1
            if won:fleet["cargo"]=load_resources({k:n//4 for k,n in data["reward_budget"].items()},capacity)
        elif event=="resources":fleet["cargo"]=load_resources(data["reward_budget"],capacity)
        elif event=="ships":
            found=self._expedition_found_ships(fleet)
            if not found:fleet["cargo"]=load_resources(data["reward_budget"],capacity)
        message={"resources":t("Znaleziono surowce."),"ships":t("Odnaleziono porzucone jednostki.") if found else t("Znaleziono surowce."),
                 "empty":t("Poszukiwania nie przyniosły znalezisk."),"delay":t("Po opóźnieniu flota zakończyła poszukiwania."),
                 "patrol":t("Pokonano patrol Roju.") if won else t("Spotkanie z patrolem Roju zakończyło się odwrotem lub utratą floty.")}[event]
        if found:message+=" "+t("Odzyskane statki: {0}.").format(", ".join(str(specs[k][0])+" ×"+str(n) for k,n in found.items()))
        message+=" "+t("Ładunek: metal {0}, kryształy {1}, paliwo {2}. Kryształy Roju: {3}. Znaleziska zostaną rozładowane po powrocie.").format(fleet["cargo"]["metal"],fleet["cargo"]["crystal"],fleet["cargo"]["fuel"],fleet.get("swarm_crystals",0))
        if replay is not None:replay.update(cargo=dict(fleet["cargo"]),swarm_crystals=fleet.get("swarm_crystals",0),swarm_eradicated=False,swarm_destruction_bonus=0)
        self._report(fleet["owner_id"],t("Raport ekspedycji"),message,ART,fleet.get("swarm_crystals",0),replay=replay,report_kind="expedition")
        if sum(fleet["ships"].values()):self._expedition_return(fleet)
        else:self.data["fleets"].pop(fleet["id"],None)
        return True
