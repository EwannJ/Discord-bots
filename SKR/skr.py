import asyncio
import base64
import hashlib
import logging
import os
import secrets
import time

import aiohttp
import discord
from aiohttp import web
from discord import app_commands
from discord.ext import commands
from pyngrok import conf, ngrok

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("skr_bot")

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
TOKEN = "MTUyNTkyODE3NjI1MTgzNDYwOA.GER9RR.e13IzvtnrxMKANf8pbZk9jt0lapqzd4FCVUmdw"
NGROK_AUTHTOKEN = "3GUXYIGXVTUZxAZJSeWcTq90K3d_6fbsjSkbJrwrU338xujhg"

for name, value in [
    ("DISCORD_TOKEN", TOKEN),
    ("NGROK_AUTHTOKEN", NGROK_AUTHTOKEN),
]:
    if not value:
        raise RuntimeError(f"Variable d'environnement manquante : {name}")

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

# ---------------------------------------------------------------------------
# ÉTAT TEMPORAIRE DES LIENS EN COURS (en mémoire, pas de base de données)
# ---------------------------------------------------------------------------
# state -> {code_verifier, discord_user_id, guild_id, created_at}
PENDING_LOGINS: dict[str, dict] = {}
LOGIN_TIMEOUT_SECONDS = 600  # 10 minutes


def _cleanup_expired_logins():
    now = time.time()
    expired = [
        state
        for state, data in PENDING_LOGINS.items()
        if now - data["created_at"] > LOGIN_TIMEOUT_SECONDS
    ]
    for state in expired:
        PENDING_LOGINS.pop(state, None)


def _generate_pkce_pair() -> tuple[str, str]:
    """Retourne (code_verifier, code_challenge) pour PKCE (méthode S256)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def sanitise_name(raw_name: str) -> str:
    def format_part(part: str) -> str:
        if "-" in part:
            return "-".join(
                section[:1].upper() + section[1:].lower()
                for section in part.split("-")
            )
        return part[:1].upper() + part[1:].lower()

    return " ".join(format_part(part) for part in raw_name.split(" ") if part)


# ---------------------------------------------------------------------------
# DISCORD BOT
# ---------------------------------------------------------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents, help_command=None)


class LinkAccountView(discord.ui.View):
    """Vue persistante avec le bouton 'Lier mon compte vAMSYS'."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Lier mon compte vAMSYS",
        style=discord.ButtonStyle.primary,
        custom_id="link-vamsys-account",
    )
    async def link_account(self, interaction: discord.Interaction, button: discord.ui.Button):
        _cleanup_expired_logins()

        if str(interaction.guild_id) not in SERVERS:
            await interaction.response.send_message(
                "Ce serveur n'est pas configuré correctement. Contactez un administrateur.",
                ephemeral=True,
            )
            return

        code_verifier, code_challenge = _generate_pkce_pair()
        state = secrets.token_urlsafe(32)

        PENDING_LOGINS[state] = {
            "code_verifier": code_verifier,
            "discord_user_id": interaction.user.id,
            "guild_id": interaction.guild_id,
            "created_at": time.time(),
        }

        params = {
            "client_id": VAMSYS_CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": VAMSYS_SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        query_string = "&".join(f"{k}={aiohttp.helpers.quote(v, safe='')}" for k, v in params.items())
        authorize_url = f"{VAMSYS_AUTHORIZE_URL}?{query_string}"

        link_view = discord.ui.View()
        link_view.add_item(
            discord.ui.Button(
                label="Se connecter à vAMSYS",
                style=discord.ButtonStyle.link,
                url=authorize_url,
            )
        )

        await interaction.response.send_message(
            "Clique sur le bouton ci-dessous, connecte-toi à vAMSYS et autorise l'accès. "
            "Ton pseudo et ton rôle seront mis à jour automatiquement juste après — "
            "tu n'as rien d'autre à faire ici.",
            view=link_view,
            ephemeral=True,
        )


@bot.tree.command(name="createrequestbutton", description="Crée le bouton de liaison de compte dans ce salon.")
@app_commands.checks.has_permissions(manage_guild=True)
async def create_request_button(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.send(view=LinkAccountView())
    await interaction.delete_original_response()


@bot.tree.command(name="ping", description="Voir le ping du bot")
@app_commands.checks.has_permissions(manage_messages=True)
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong ! Ma latence est de **{latency}ms**.", ephemeral=True)


async def apply_pilot_to_member(guild: discord.Guild, member: discord.Member, pilot_data: dict) -> tuple[bool, str]:
    """Applique le pseudo + les rôles à partir des données pilote vAMSYS. Retourne (succès, message)."""
    server_config = SERVERS.get(str(guild.id))
    if server_config is None:
        return False, "Serveur non configuré."

    first_name = pilot_data.get("first_name") or pilot_data.get("firstName") or ""
    last_name = pilot_data.get("last_name") or pilot_data.get("lastName") or ""
    pilot_id = pilot_data.get("username") or pilot_data.get("pilot_id") or ""

    full_name = sanitise_name(f"{first_name} {last_name}".strip())
    separator = server_config["nickSeparator"]

    try:
        await member.edit(nick=f"{full_name}{separator}{pilot_id}".strip())
    except discord.Forbidden:
        return False, "Le bot n'a pas la permission de modifier le pseudo (rôle du bot trop bas)."

    role_removal_cfg = server_config.get("roleRemoval", {"enabled": False, "roleId": []})
    user_role_ids = [r.id for r in member.roles if r.id != guild.id]

    if role_removal_cfg.get("enabled", False):
        to_remove = set(str(r) for r in role_removal_cfg.get("roleId", []))
        user_role_ids = [rid for rid in user_role_ids if str(rid) not in to_remove]

    for role_id in server_config.get("accessRoleId", []):
        rid = int(role_id)
        if rid not in user_role_ids:
            user_role_ids.append(rid)

    try:
        new_roles = [guild.get_role(rid) for rid in user_role_ids]
        new_roles = [r for r in new_roles if r is not None]
        await member.edit(roles=new_roles)
    except discord.Forbidden:
        return False, "Le bot n'a pas la permission de modifier les rôles (rôle du bot trop bas)."

    return True, "OK"


# ---------------------------------------------------------------------------
# SERVEUR WEB (callback OAuth vAMSYS)
# ---------------------------------------------------------------------------
async def handle_callback(request: web.Request) -> web.Response:
    _cleanup_expired_logins()

    code = request.query.get("code")
    state = request.query.get("state")
    error = request.query.get("error")

    if error:
        return web.Response(
            text=f"Autorisation refusée ou erreur vAMSYS : {error}. Tu peux fermer cette page.",
            status=400,
        )

    if not code or not state or state not in PENDING_LOGINS:
        return web.Response(
            text="Lien invalide ou expiré. Retourne sur Discord et reclique sur le bouton.",
            status=400,
        )

    login_data = PENDING_LOGINS.pop(state)

    # --- Échange du code contre un token (pas de client_secret : client PKCE public) ---
    async with aiohttp.ClientSession() as session:
        token_payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": VAMSYS_CLIENT_ID,
            "code_verifier": login_data["code_verifier"],
        }

        try:
            async with session.post(VAMSYS_TOKEN_URL, data=token_payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    log.error("Échec de l'échange de token vAMSYS (%s) : %s", resp.status, body)
                    return web.Response(text="Erreur lors de la connexion à vAMSYS. Réessaie.", status=502)
                token_data = await resp.json()
        except aiohttp.ClientError as exc:
            log.exception("Erreur réseau lors de l'échange de token : %s", exc)
            return web.Response(text="Erreur réseau, réessaie plus tard.", status=502)

        access_token = token_data.get("access_token")
        if not access_token:
            return web.Response(text="Réponse vAMSYS invalide (pas de token).", status=502)

        # --- Récupération du profil pilote ---
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            async with session.get(VAMSYS_PILOT_ME_URL, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    log.error("Échec de récupération du profil pilote (%s) : %s", resp.status, body)
                    return web.Response(
                        text=(
                            "Impossible de récupérer ton profil vAMSYS.\n\n"
                            f"[DEBUG] URL appelée : {VAMSYS_PILOT_ME_URL}\n"
                            f"[DEBUG] Code HTTP : {resp.status}\n"
                            f"[DEBUG] Réponse vAMSYS : {body}"
                        ),
                        status=502,
                    )
                pilot_data = await resp.json()
                log.info("Profil pilote reçu : %s", pilot_data)
        except aiohttp.ClientError as exc:
            log.exception("Erreur réseau lors de la récupération du profil : %s", exc)
            return web.Response(text=f"Erreur réseau, réessaie plus tard.\n\n[DEBUG] {exc}", status=502)

    # --- Application du pseudo/rôle côté Discord ---
    guild = bot.get_guild(login_data["guild_id"])
    if guild is None:
        return web.Response(text="Le bot ne trouve plus ce serveur Discord.", status=500)

    member = guild.get_member(login_data["discord_user_id"])
    if member is None:
        return web.Response(text="Tu ne sembles plus être membre de ce serveur Discord.", status=400)

    success, message = await apply_pilot_to_member(guild, member, pilot_data)

    if success:
        return web.Response(
            text="✅ Compte lié avec succès ! Ton pseudo et ton rôle ont été mis à jour. "
            "Tu peux fermer cette page et retourner sur Discord."
        )
    else:
        log.error("Échec de l'application du pseudo/rôle pour %s : %s", member, message)
        return web.Response(text=f"Connexion réussie, mais erreur côté Discord : {message}", status=500)


async def start_web_server():
    app = web.Application()
    app.router.add_get("/vamsys/callback", handle_callback)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", LOCAL_PORT)
    await site.start()
    log.info("Serveur web local démarré sur le port %s", LOCAL_PORT)


def start_ngrok_tunnel():
    conf.get_default().auth_token = NGROK_AUTHTOKEN
    tunnel = ngrok.connect(addr=LOCAL_PORT, domain=NGROK_DOMAIN)
    log.info("Tunnel ngrok ouvert : %s", tunnel.public_url)


@bot.event
async def on_ready():
    print("SKR online !")

    bot.add_view(LinkAccountView())

    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} commandes syncronisées")
    except Exception as e:
        print(f"⚠️ Erreur lors de la synchronisation des commandes : {e}")


async def main():
    start_ngrok_tunnel()
    await start_web_server()
    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())