import os

# ---------------------------------------------------------------------------
# SECRETS — variables d'environnement (jamais en clair dans le code)
# ---------------------------------------------------------------------------
# À définir sur Orion (panel -> Startup / Variables) :
#   DISCORD_TOKEN=...
#   NGROK_AUTHTOKEN=...
#
# Pas de VAMSYS_CLIENT_SECRET : le client OAuth "Authorization Code + PKCE"
# est un client PUBLIC. La sécurité repose sur le code_verifier/code_challenge
# (PKCE), pas sur un secret partagé — vAMSYS ne t'en fournit donc pas.
TOKEN = os.environ.get("DISCORD_TOKEN")
NGROK_AUTHTOKEN = os.environ.get("NGROK_AUTHTOKEN")

for _name, _value in [
    ("DISCORD_TOKEN", TOKEN),
    ("NGROK_AUTHTOKEN", NGROK_AUTHTOKEN),
]:
    if not _value:
        raise RuntimeError(f"Variable d'environnement manquante : {_name}")

# ---------------------------------------------------------------------------
# CONFIG NON SENSIBLE
# ---------------------------------------------------------------------------

# Client ID du client OAuth "Authorization Code + PKCE" (pas le "968", qui
# est un client Client Credentials différent)
VAMSYS_CLIENT_ID = "973"

# Domaine statique ngrok (gratuit, fixe tant que tu ne le supprimes pas)
NGROK_DOMAIN = "barbecue-avert-reckless.ngrok-free.dev"

# Port local sur lequel le mini-serveur web tourne (ngrok fait le pont vers
# l'extérieur, donc ce port n'a pas besoin d'être ouvert publiquement sur Orion)
LOCAL_PORT = 8080

REDIRECT_URI = f"https://{NGROK_DOMAIN}/vamsys/callback"

# ⚠️ À CONFIRMER dans https://vamsys.io/docs/pilot (section "Authorize" et
# section "Token") — ce sont les valeurs les plus probables suivant la
# convention OAuth2 déjà confirmée pour /oauth/token, mais pas encore vérifiées
# mot pour mot dans la doc v3.
VAMSYS_AUTHORIZE_URL = "https://vamsys.io/oauth/authorize"
VAMSYS_TOKEN_URL = "https://vamsys.io/oauth/token"
# Endpoint confirmé dans la doc vAMSYS (Server: https://vamsys.io/api/v3/pilot)
VAMSYS_PILOT_ME_URL = "https://vamsys.io/api/v3/pilot/profile"

VAMSYS_SCOPES = "identity:basic identity:discord pilot:read"

# Configuration par serveur Discord : pseudo + rôles à appliquer
SERVERS = {
    "1416847953783558327": {
        "nickSeparator": " | ",
        "accessRoleId": ["1525912891121991822"],
        "roleRemoval": {
            "enabled": False,
            "roleId": [],
        },
    },
}

# Durée de vie max d'une tentative de liaison en attente (secondes)
LOGIN_TIMEOUT_SECONDS = 600  # 10 minutes
