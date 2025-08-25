# PromoTronik — Pro (sources marchands)

Ce pack utilise **python-amazon-paapi (5.0.1)** (PyPI officiel) pour Amazon, et des **feeds AWIN** pour Fnac/Darty.
1) Ajoute tes secrets GitHub (AMAZON_ACCESS_KEY/SECRET_KEY/PARTNER_TAG, AWIN_FEED_*...). 
2) Laisse `awin.enabled: false` si tu n'as pas encore les feeds. 
3) Workflow: pip install -r requirements.txt → python generate_site.py.
