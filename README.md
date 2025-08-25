# PromoTronik

Ce dépôt contient le code source d'un micro-agrégateur d'affiliation qui récupère des flux RSS de bons plans (High‑tech & bricolage), ajoute vos tags affiliés et publie automatiquement une page statique. L'hébergement se fait gratuitement via GitHub Pages, et la mise à jour est déclenchée toutes les heures grâce à GitHub Actions.

## Mise en place

1. Clonez ce dépôt ou téléversez son contenu sur un nouveau dépôt GitHub public.
2. Renseignez vos identifiants affiliés dans `feeds.yaml` (champ `affiliate_rules`).
3. Activez GitHub Actions dans l'onglet **Actions** du dépôt.
4. Configurez GitHub Pages dans **Settings → Pages** : Source = `Deploy from a branch`, Branch = `main`, Dossier = `/docs`.
5. Lancez manuellement le workflow dans l'onglet **Actions** (Bouton *Run workflow*) pour la première génération.

Le site sera ensuite disponible à l'URL `https://<votre-pseudo>.github.io/<nom-du-repo>/` et mis à jour automatiquement chaque heure.

## Configuration

Le fichier `feeds.yaml` vous permet de :
- définir les flux RSS à surveiller (`feeds`),
- configurer vos tags affiliés (`affiliate_rules`),
- personnaliser le titre, la description et le message de divulgation du site (`site`),
- ajuster les mots-clés à inclure ou exclure (`filters`).

Veillez à respecter les conditions d'utilisation des programmes d'affiliation, notamment l'obligation de divulguer la nature rémunérée des liens.
