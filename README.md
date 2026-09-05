# TCL MagiConnect pour Home Assistant

Intégration locale expérimentale du protocole **MagiConnect / T-Cast** utilisé
par TCL : UDP 6537 et TCP 6553. Aucun ADB, compte cloud ou commande shell dans
l'intégration. Configuration depuis l'interface Home Assistant.

**Préversion 0.1.0 : pas encore testée sur un téléviseur réel.** Le protocole a été
identifié par analyse statique de MagiConnect Android 2.0.199 et testé sur des
serveurs simulés. La compatibilité d'une TCL Google TV 2026 reste à confirmer.
Le modèle exact, le firmware, la région et la présence du service TV comptent.
Un millésime Google TV ne suffit pas à garantir le support.

## Fonctions de cette préversion

| Fonction | Implémentation | Limite actuelle |
| --- | --- | --- |
| Découverte native | Recherche UDP à la demande dans la configuration | Même réseau local ; saisie manuelle possible |
| Identification | Réponse TCL 159, modèle, firmware et identifiant stable | Pas de confirmation matérielle |
| Chiffrement | Clair ou AES-CBC selon la négociation TV | Algorithmes inconnus refusés |
| Télécommande | Navigation, volume, chaînes, couleurs, clavier numérique, power | `power` est une bascule ; aucun état écran inventé |
| Clavier | Action `send_text`, UTF-8 | Un champ TV doit accepter la saisie ; `>>` et NUL interdits |
| Souris | Action `move_mouse`, clics via la télécommande | Dépend du modèle |
| Applications | Lecture de la liste et ouverture d'un paquet installé | Rafraîchissement à la demande ; pas d'installation d'APK |
| Vidéo | URL HTTP(S) envoyée au lecteur TCL | Vidéo directe uniquement ; pas de DRM, ni de téléversement |
| Lecture/pause/stop | Commandes du lecteur MagiConnect | Ne pilotent pas nécessairement Netflix/YouTube |
| Capture | Action retournant l'URL locale de la capture produite par la TV | Fonction à valider ; aucun téléchargement automatique |
| Diagnostic | Disponibilité du service et diagnostic exportable | Aucun état marche/arrêt ou média global supposé |

Photos, musique, état de lecture global, réveil réseau, cloud TCL Home et
appairage Google TV Remote v2 ne sont **pas implémentés** dans cette préversion.
Aucun échange de PIN TCL n'a été identifié dans la branche native implémentée ;
la négociation 159 ne doit pas être présentée comme un appairage sécurisé.

## Installation HACS

1. Ajouter `https://github.com/Micpi/tcl-magiconnect` comme dépôt personnalisé,
   catégorie **Intégration**.
2. Activer l'affichage des préversions si nécessaire, puis installer la préversion.
3. Redémarrer Home Assistant.
4. Dans **Paramètres → Appareils et services → Ajouter une intégration**, chercher
   **TCL MagiConnect**.
5. Ouvrir MagiConnect/T-Cast sur la TV, puis lancer la découverte ou saisir son IP.

Installation manuelle : copier `custom_components/tcl_magiconnect` dans le dossier
`custom_components` de Home Assistant, puis redémarrer. Home Assistant 2025.12+
est requis ; la CI cible aussi Home Assistant 2026.9.0.

L'ajout vérifie une vraie réponse au protocole : un port ouvert ne suffit pas.
Une TV inaccessible n'est pas ajoutée avec de faux succès. Une entrée existante
sera réessayée automatiquement si le téléviseur est indisponible au démarrage.
Le menu **Reconfigurer** permet de modifier son adresse en vérifiant son identité.

## Utilisation

Adapter les identifiants d'entités à ceux créés chez vous.

```yaml
action: remote.send_command
target:
  entity_id: remote.tcl_magiconnect_remote
data:
  command: [home, right, ok]
  num_repeats: 1
  delay_secs: 0.2
```

Commandes : `up`, `down`, `left`, `right`, `ok`, `back`, `home`, `menu`, `power`,
`volume_up`, `volume_down`, `mute`, `channel_up`, `channel_down`, `source`,
`guide`, `search`, `red`, `green`, `yellow`, `blue`, `0` à `9`, `enter`,
`backspace`, `mouse_left`, `mouse_right` et autres touches listées dans l'attribut
`commands` de la télécommande. **`enter` (68) et `ok` (15) sont différents.**
Les codes Android `KEYCODE_*` ne sont pas des codes MagiConnect.

```yaml
action: tcl_magiconnect.send_text
target:
  entity_id: remote.tcl_magiconnect_remote
data:
  text: "Bonjour depuis Home Assistant"
```

```yaml
action: tcl_magiconnect.move_mouse
target:
  entity_id: remote.tcl_magiconnect_remote
data:
  x: 30
  y: -10
```

Exécuter `tcl_magiconnect.refresh_apps` sur la télécommande pour remplir les
sources du lecteur multimédia. On peut aussi ouvrir directement un paquet :

```yaml
action: tcl_magiconnect.launch_app
target:
  entity_id: remote.tcl_magiconnect_remote
data:
  package: com.google.android.youtube.tv
```

```yaml
action: media_player.play_media
target:
  entity_id: media_player.tcl_magiconnect
data:
  media_content_type: video
  media_content_id: "http://192.168.1.10:8080/video.mp4"
```

La TV doit pouvoir lire cette URL directement. Le lancement interrompt le lecteur
MagiConnect précédent. Les URL `media-source://` ne sont pas résolues.

Dans un script, récupérer une URL de capture avec une variable de réponse :

```yaml
action: tcl_magiconnect.get_screenshot_url
target:
  entity_id: remote.tcl_magiconnect_remote
response_variable: capture
```

Home Assistant renvoie le résultat de l'entité ciblée, contenant `url`.
Le refus de la TV ou une URL visant un autre hôte produit une erreur.

## État et compatibilité

La télécommande et le lecteur peuvent afficher **Inconnu** tout en acceptant des
commandes : le protocole ne fournit pas ici de preuve de l'état écran ou du média
actif. Le capteur de diagnostic indique si le service répond. Une TV en veille
peut continuer à répondre ; une TV allumée peut avoir son service MagiConnect fermé.
`remote.turn_on` et `remote.turn_off` refusent donc de prétendre faire une action
idempotente. Utiliser la touche `power` pour une bascule explicite.

Les sessions sont courtes : négociation avant chaque opération, fermeture ensuite.
Les opérations sont sérialisées et une commande échouée n'est jamais rejouée
automatiquement. Un envoi réussi signifie que les octets ont été écrits, pas que
le téléviseur a exécuté chaque action. Certaines fonctions peuvent être absentes
ou bloquées par le firmware malgré une identification réussie.

Si le service natif n'existe pas sur votre TV, l'intégration officielle Home Assistant
[Android TV Remote](https://www.home-assistant.io/integrations/androidtv_remote/)
constitue une couche secondaire sans ADB, avec son propre appairage PIN.
Cette préversion ne bascule pas automatiquement vers cet autre protocole.

## Validation sur place

Voir [le guide de validation](docs/VALIDATION.md) et [les observations du protocole](docs/PROTOCOL.md).
Le dossier `.research/` contient uniquement les matériaux locaux d'analyse ; les APK,
les sources décompilées et les captures réseau ne sont pas distribués avec le projet.

```sh
python -m pip install -r requirements-dev.txt
python tools/probe.py --host 192.168.1.50
pytest tests/unit -q
```

L'outil `probe.py` effectue seulement la découverte ou l'identification, jamais une
touche de télécommande. Il doit tourner sur le LAN du téléviseur.

Ce projet communautaire n'est pas affilié à TCL.
