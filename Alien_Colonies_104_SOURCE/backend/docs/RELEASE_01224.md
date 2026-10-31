# Alien Colonies 0.12.24 / Android 91

Galaxy navigation and new-mission destination selection open at the maximum supported focus zoom: 4.5x for the expanded five-ring map. Both focus the active colony. Manual zoom-out, whole-map reset, panning and resizing remain available. Web cache revisions and release hashes include the new camera behavior. No world geometry, routes or account data change.

Android uses GalaxyMap.MAX_ZOOM as the shared DEFAULT_FOCUS_ZOOM; FleetNavigation derives its destination zoom from the same constant. Firebase notification display behavior remains as implemented in Android90; foreground suppression was deferred by the owner.

Firebase project alien-colonies now has the Android application com.conradmafer.aliencolonies registered and FCM HTTP v1 enabled. The existing server service account has the Firebase Cloud Messaging API Admin role. Railway holds the public Android configuration and references the existing server service-account secret for FCM; no private key is stored in the repository. Activation requires the deployment containing those environment variables. A physical-device delivery test remains outstanding.

Validation: 30 browser navigation/fleet unit checks passed; 101 actual native Godot UI/optical-core checks passed, including maximum initial zoom and matching centred cameras in Galaxy and the mission picker at 720x1280 and 720x1600. No production mutations were used by these tests.
