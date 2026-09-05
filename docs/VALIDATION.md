# Validation sur une TCL Google TV 2026

Le propriétaire n'étant pas actuellement sur le LAN, aucune validation matérielle
n'a été réalisée lors de la création. Il ne faut pas annoncer le modèle comme
compatible avant ce contrôle.

1. Relever le modèle exact, le pays et le firmware dans les paramètres de la TV.
2. Ouvrir MagiConnect/T-Cast sur la TV. Vérifier que l'application téléphone TCL
   détecte et commande effectivement cette TV sur le même réseau.
3. Installer la préversion et saisir l'adresse IP dans le config flow. Une erreur
   TCP 6553 ne doit pas être contournée en choisissant arbitrairement TCP 4123.
4. Essayer une touche `right` ou `back`, puis volume. Ne tester `power` qu'en
   ayant la télécommande physique à portée de main.
5. Ouvrir un champ de recherche, tester `send_text` avec un texte non sensible.
6. Exécuter `refresh_apps`, vérifier que la liste correspond à la TV, puis ouvrir
   une application installée. Tester souris/capture seulement si disponibles.
7. Tester une URL vidéo directe accessible à la TV, puis pause/reprise/arrêt.
8. Fermer et rouvrir le service, changer l'adresse via **Reconfigurer**, redémarrer
   Home Assistant et vérifier la récupération sans double commande.

Pour diagnostiquer avant installation, depuis un ordinateur sur le LAN :

```sh
python -m pip install cryptography
python tools/probe.py
python tools/probe.py --host 192.168.1.50
```

La première commande Python affiche les appareils découverts (IP et nom locaux).
La seconde ne fait que l'identification et produit un résultat sans MAC ni numéro
de série. Ne pas ouvrir de ports WAN : Home Assistant doit joindre directement
la TV. Si aucune réponse native n'est reçue alors que l'application téléphone
fonctionne, une capture limitée aux échanges téléphone ↔ TV pendant découverte,
connexion et une touche non sensible permettra d'étudier une autre branche du
protocole. Ne pas publier de capture brute contenant des identifiants personnels.

Les tests automatisés simulent des échanges ; ils ne constituent pas une preuve
de compatibilité matérielle. Les champs inconnus doivent rester inconnus.
