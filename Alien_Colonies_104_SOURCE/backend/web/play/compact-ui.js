import {getLanguage, t} from './i18n.js?v=0111';
import {storageBlocksCost} from './resource-storage.js?v=01218-storage';

const labels = {
  newMission: ['Nowa misja','New mission','Neue Mission','Nueva misión','Nouvelle mission'],
  construction: ['Budowa','Construction','Bau','Construcción','Construction'],
  ships: ['Statki','Ships','Schiffe','Naves','Vaisseaux'],
  defenses: ['Obrona','Defenses','Verteidigung','Defensas','Défenses'],
  fleet: ['Flota','Fleet','Flotte','Flota','Flotte'],
  planet: ['Planeta','Planet','Planet','Planeta','Planète'],
  activeMissions: ['Aktywne misje','Active missions','Aktive Missionen','Misiones activas','Missions actives'],
  protected: ['Pod ochroną','Protected','Geschützt','Protegido','Protégée'],
  map: ['Mapa','Map','Karte','Mapa','Carte'],
  system: ['Układ','System','System','Sistema','Système'],
  changeDestination: ['Zmień cel na mapie','Change destination on map','Ziel auf der Karte ändern','Cambiar destino en el mapa','Changer la destination sur la carte'],
  chooseTarget: ['Wybierz cel','Choose a target','Ziel wählen','Elegir destino','Choisir une cible'],
  details: ['Szczegóły','Details','Details','Detalles','Détails'],
  dyson: ['Sfera Dysona','Dyson Sphere','Dyson-Sphäre','Esfera de Dyson','Sphère de Dyson'],
  wormhole: ['Tunel czasoprzestrzenny','Spacetime Wormhole','Raumzeit-Wurmloch','Agujero de gusano','Trou de ver spatio-temporel'],
  dysonDescription: ['Zbiera energię gwiazdy. Rozbudowa zasila kolonię, umożliwia budowę tytanów i ładuje tunel czasoprzestrzenny.','Collects stellar energy. Upgrades power the colony, enable titan construction and charge the wormhole.','Sammelt Sternenenergie. Ausbaustufen versorgen die Kolonie, ermöglichen Titanen und laden das Wurmloch.','Recoge energía estelar. Las mejoras abastecen la colonia, permiten construir titanes y cargan el agujero de gusano.','Collecte l’énergie stellaire. Les améliorations alimentent la colonie, permettent de construire des titans et chargent le trou de ver.'],
  wormholeDescription: ['Otwiera krótkotrwałe połączenie z wybraną planetą, również w innej galaktyce. Podróż zużywa energię Sfery Dysona.','Opens a temporary link to a chosen planet, including another galaxy. Travel consumes Dyson Sphere energy.','Öffnet eine vorübergehende Verbindung zu einem Planeten, auch in einer anderen Galaxie. Die Reise verbraucht Energie der Dyson-Sphäre.','Abre una conexión temporal a un planeta, incluso en otra galaxia. El viaje consume energía de la esfera de Dyson.','Ouvre un passage temporaire vers une planète, même dans une autre galaxie. Le voyage consomme l’énergie de la sphère de Dyson.'],
  openWormhole: ['Otwórz tunel','Open wormhole','Wurmloch öffnen','Abrir agujero de gusano','Ouvrir le trou de ver'],
  projectOrigin: ['Centrum projektu','Project origin','Projektzentrum','Centro del proyecto','Centre du projet'],
  freeFields: ['wolnych pól','free slots','freie Felder','espacios libres','emplacements libres'],
  readyIn: ['Gotowość za','Ready in','Bereit in','Listo en','Prêt dans'],
  energy: ['Energia','Energy','Energie','Energía','Énergie'],
  stage: ['Etap','Stage','Stufe','Etapa','Étape'],
  requirementsUnmet: ['Nie spełniono wymagań projektu.','Project requirements are not met.','Projektvoraussetzungen nicht erfüllt.','No se cumplen los requisitos del proyecto.','Les conditions du projet ne sont pas remplies.'],
  locked: ['Zablokowane','Locked','Gesperrt','Bloqueado','Verrouillée'],
  completed: ['Ukończono','Complete','Fertig','Completado','Terminé'],
  startBuild: ['Rozpocznij budowę','Start construction','Bau starten','Iniciar construcción','Lancer la construction'],
};

export function uiText(key) {
  const index = ['pl','en','de','es','fr'].indexOf(getLanguage());
  return labels[key]?.[index < 0 ? 1 : index] || key;
}

export function projectReason(item, state) {
  // Unmet requirements are already listed on the card. Keep other reasons,
  // including resource shortages and busy queues, once requirements are met.
  const reason = storageBlocksCost(state, item.cost)
    ? t('Rozbuduj skarbiec: pojemność magazynu jest za mała')
    : item.reason || '';
  const requirementsShown = (item.requirements || []).some(req => req.met === false);
  const redundant = reason.startsWith(t('Wymaga:')) || reason === uiText('requirementsUnmet');
  return requirementsShown && redundant ? '' : reason;
}

export function resetMissionDraft(model) {
  model.fleetTarget = '';
  model.fleetSystemId = '';
  model.fleetMission = 'scout';
  model.fleetTravelMode = 'normal';
  model.fleetPreview = null;
  model.fleetDraft = null;
  model.missionSelecting = true;
  model.galaxyMode = 'map';
}

export function protectedPlanet(planet, now) {
  return Number(planet.protected_until) > Number(now);
}
