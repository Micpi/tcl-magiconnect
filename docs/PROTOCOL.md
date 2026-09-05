# Observations MagiConnect / T-Cast

Analyse du 5 septembre 2026, pour l'interopérabilité locale. Le code Python est une
implémentation indépendante ; aucun code Java décompilé ni binaire TCL n'est publié.

## Sources et méthode

- [Fiche officielle Android du téléphone](https://play.google.com/store/apps/details?id=com.magiconnect.tcast).
- [Fiche officielle du service TV](https://play.google.com/store/apps/details?id=com.tcl.magiconnectfree).
- [Manuel TCL C745/C845](https://www.tcl.com/content/dam/brandsite/region/australia/AU_Mediacenter/download/C745_C845_User_Manual.pdf) : télécommande sur le même LAN.
- APK téléphone archivé par [Aptoide](https://magiconnect.en.aptoide.com/app),
  package `com.magiconnect.tcast`, version `2.0.199`, code `201990`.
  Base : 58 549 131 octets, SHA-256
  `3fed2966a0a236e81dc3382fef55e2372ac4433a9e29563a09c37c34abbfc02f`.
- Métadonnées de l'archive : certificat annoncé `CN=R&D, OU=TCL, O=TCL,
  L=ShenZhen, ST=GuangDong, C=CN`, SHA-1 annoncé
  `B5:DB:6E:BB:6B:15:24:5F:0D:EA:BB:31:34:56:44:4A:D7:3C:9E:12`.
  Cette identité est rapportée par l'archive ; elle n'est pas une vérification
  indépendante de la signature APK par ce projet.
- Split ARM64 : MD5 de l'archive `7f8b48a6164025d6d7e19ceb92d8ef97`,
  contenant `lib/arm64-v8a/libjnitool.so`.
- JADX 1.5.6 pour le Java ; pyelftools et Capstone pour le désassemblage ARM64.
  L'APK n'a pas été exécuté. La décompilation complète rapporte 238 erreurs,
  principalement hors du périmètre ; les méthodes de transport citées ci-dessous
  sont lisibles. Les erreurs empêchent de prétendre à une analyse exhaustive.

Les premières pistes publiques étaient
[featherbear/tcl-link](https://github.com/featherbear/tcl-link),
[NickCis/node-tcl-remote](https://github.com/NickCis/node-tcl-remote) et
[jarvis2f/tcl-remote](https://github.com/jarvis2f/tcl-remote).
Les deux premières concernent notamment le XML TCP 4123, **différent** du transport
ci-dessous. Le troisième décrit UDP 6537/TCP 6553 sur une TCL 65Q10L Pro ; cela
ne prouve pas la compatibilité d'une Google TV internationale 2026.

## Localisation des preuves dans l'APK

Préfixe Java : `com.tcl.tcastsdk.mediacontroller`, dans `classes6.dex`.

| Élément | Classe/méthode observée | Format |
| --- | --- | --- |
| Ports | `device.IpMessageConst` | UDP 6537, TCP 6553 |
| Découverte | `discover.TCLDeviceScanner`, `discover.IpMessageProtocol` | Champs `:` ; rôle `PHONE` / `TV` |
| Trames sortantes | `device.tcp.AbstractPacketWriter.writeMyUTF` | Entier big-endian 32 bits puis octets UTF-8 ou chiffrés |
| Trames entrantes | `device.tcp.PacketReader` | Même cadrage ; limite < 1 MiB |
| Identification | `device.cmd.InquiryDeviceInfoCommand.pack` | `159>>nom>>1>>uuid>>1` |
| Réponse identification | `device.protocol.ProtocolHandlerV6.parseGetClientTypeCmd` | Champs décrits ci-dessous |
| Touches | `device.cmd.RemoteControlKeyCmd` | `149>>code` |
| Texte | `device.cmd.RemoteControlInputCmd` | `155>>texte` |
| Souris | `device.cmd.RemoteControlMouseCmd` | `151>>x>>y` |
| Applications | `AppManagerProxy`, `device.cmd.AppManagerCmd` | `223>>GET`, `223>>OPEN>>paquet` |
| Liste d'apps | `bean.TVAppsInfo.parseInfoList` | Apps séparées par `>` ; attributs par `::` |
| Capture | `TCLShotPicProxy`, `device.cmd.ShotPicCmd` | `225>>`, réponse `225>>0>>URL` si succès |
| Vidéo | `TCLVideoPlayerProxy.play`, `bean.VideoInfo.getInfo` | Stop, préparation Video, lecture ; sous-champs `->` |
| Vie de session | `device.heartbeat.HeartbeatRequest` | `150>>` ; inutile entre opérations avec les sessions courtes actuelles |

### Découverte

Requête terminée par NUL :

```text
1:<timestamp_ms>:Home Assistant:PHONE:1:Home Assistant:<client_id>:0:0\0
```

Dans une annonce TV, les champs de base contiennent version, timestamp, nom,
type et commande. L'annonce `2` indique un départ et doit être ignorée. Les
champs additionnels contiennent notamment les fonctions et des MAC. `&#058`
représente `:` dans le nom ou une MAC. La réponse UDP est un candidat : le
config flow confirme toujours le protocole par TCP avant d'enregistrer une TV.

### Identification TCP

La première requête et sa réponse sont en clair. Réponse 159, indices à partir de 0 :

| Index | Sens observé |
| --- | --- |
| 0 | `159` |
| 1 | Type de client TV |
| 2 | Code et nom de version du service, séparés par `:` |
| 3 | Version logicielle |
| 4 | Numéro de modèle/appareil |
| 5 | MAC |
| 6 | `algorithmType` : absent/vide → -1 ; 1 → AES |
| 7–9 | MAC Bluetooth, type TV, magasin TV |
| 10 | Code de fonctions de la négociation |
| 11–18 | Langue, série, code client, pays et informations réseau supplémentaires |

Attention : le code de fonctions UDP et celui de la réponse 159 ont des traitements
différents dans le SDK. Ils ne sont pas interprétés comme une unique liste de bits
garantissant les capacités dans cette préversion.

Le lecteur accepte les modes clairs -1/0 et AES 1. Tout autre mode est refusé.
La présence du champ `secret=1` dans la requête ne démontre pas un mécanisme de PIN.
Des branches de contrôle supplémentaires existent dans l'application (vérification
de paquets, Bluetooth, autres services) ; elles ne sont pas réimplémentées ici.

### AES

`util.SecurityUtil.AES` utilise `AES/CBC/PKCS5Padding` (padding PKCS7 pour AES).
Le Java obtient sa clé dans `util.NativeUtil.getKey()` via `libjnitool.so`.

- Clé UTF-8 de 16 octets : `tnscreentnscreen`.
- IV de 16 octets : `1234567890abcdef1234567890abcdef` en hexadécimal.
- La longueur de trame porte sur le **texte chiffré**, pas sur les caractères.

Dans le split ARM64 analysé, `getKey` à l'adresse virtuelle `0x77c` utilise
`NewStringUTF` avec les données à `0x548`. `getIV` à `0x6e8` copie les 16 octets
à `0x538`. Cela confirme les constantes de transport, indépendamment d'une
supposition faite à partir de chaînes isolées.

Ce chiffrement à constantes partagées ne fournit pas une authentification forte
de la TV. Le protocole est destiné au LAN ; la vérification MAC/série évite
principalement de commander par erreur un autre appareil après un changement d'IP.

### Applications et vidéo

Réponse apps : `223>>GET>><package>::<name>::<icon>::...>...`.
Un paquet ne doit pas être identifié seulement par son nom traduit.

Lecture vidéo directe :

```text
129>>
133>>Video
134>><url>-><title>->null->null->null->false->null->null
```

Les huit champs de `VideoInfo` sont URL, titre, lecteur, album, couverture,
orientation portrait, largeur, hauteur. Les champs non renseignés sont sérialisés
`null` par le code Java observé. Cette forme est implémentée mais reste à tester
sur une TV. Reprise/pause/arrêt du lecteur : `134>>`, `135>>`, `129>>`.

## Ce qui reste à établir sur la TV cible

Présence du service sur une Google TV 2026, contraintes d'autorisation, comportement
des sessions courtes, acquittement réel des touches, état écran, réveil depuis la
veille, formats photo/audio et capacités modèle par modèle. L'analyse d'une APK
téléphone, même récente, ne répond pas seule à ces questions.
