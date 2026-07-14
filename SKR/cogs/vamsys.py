import logging
import secrets
import time

import aiohttp
import discord
from aiohttp import web
from discord.ext import commands

import config
from utils import generate_pkce_pair, sanitise_name

log = logging.getLogger("skr_bot.vamsys")


class VamsysCog(commands.Cog):
    """Gère tout le flux OAuth PKCE vAMSYS : lancement du lien, callback web,
    échange de token, récupération du profil pilote et application du
    pseudo/rôle côté Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # state -> {code_verifier, discord_user_id, guild_id, created_at}
        self.pending_logins: dict[str, dict] = {}
        self._runner: web.AppRunner | None = None

    # ------------------------------------------------------------------
    # Cycle de vie du cog : démarre/arrête le mini-serveur web du callback
    # ------------------------------------------------------------------
    async def cog_load(self) -> None:
        app = web.Application()
        app.router.add_get("/vamsys/callback", self.handle_callback)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", config.LOCAL_PORT)
        await site.start()
        log.info("Serveur web local démarré sur le port %s", config.LOCAL_PORT)

    async def cog_unload(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()

    # ------------------------------------------------------------------
    # Gestion des liaisons en attente
    # ------------------------------------------------------------------
    def _cleanup_expired_logins(self) -> None:
        now = time.time()
        expired = [
            state
            for state, data in self.pending_logins.items()
            if now - data["created_at"] > config.LOGIN_TIMEOUT_SECONDS
        ]
        for state in expired:
            self.pending_logins.pop(state, None)

    def create_pending_login(self, discord_user_id: int, guild_id: int) -> tuple[str, str]:
        """Crée une tentative de liaison PKCE et retourne (state, code_challenge)."""
        self._cleanup_expired_logins()

        code_verifier, code_challenge = generate_pkce_pair()
        state = secrets.token_urlsafe(32)

        self.pending_logins[state] = {
            "code_verifier": code_verifier,
            "discord_user_id": discord_user_id,
            "guild_id": guild_id,
            "created_at": time.time(),
        }
        return state, code_challenge

    def build_authorize_url(self, state: str, code_challenge: str) -> str:
        params = {
            "client_id": config.VAMSYS_CLIENT_ID,
            "redirect_uri": config.REDIRECT_URI,
            "response_type": "code",
            "scope": config.VAMSYS_SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        query_string = "&".join(
            f"{k}={aiohttp.helpers.quote(v, safe='')}" for k, v in params.items()
        )
        return f"{config.VAMSYS_AUTHORIZE_URL}?{query_string}"

    # ------------------------------------------------------------------
    # Application du pseudo/rôle côté Discord
    # ------------------------------------------------------------------
    async def apply_pilot_to_member(
        self, guild: discord.Guild, member: discord.Member, pilot_data: dict
    ) -> tuple[bool, str]:
        server_config = config.SERVERS.get(str(guild.id))
        if server_config is None:
            return False, "Serveur non configuré."

        first_name = pilot_data.get("first_name") or pilot_data.get("firstName") or ""
        last_name = pilot_data.get("last_name") or pilot_data.get("lastName") or ""
        pilot_id = pilot_data.get("username") or pilot_data.get("pilot_id") or ""

        full_name = sanitise_name(f"{first_name} {last_name}".strip())
        separator = server_config["nickSeparator"]

        errors: list[str] = []

        # --- Pseudo : tenté indépendamment du reste (peut échouer sur le
        # propriétaire du serveur quelle que soit la hiérarchie des rôles) ---
        try:
            await member.edit(nick=f"{full_name}{separator}{pilot_id}".strip())
        except discord.Forbidden:
            errors.append(
                "pseudo non modifié (rôle du bot trop bas, ou membre = propriétaire du serveur)"
            )

        # --- Rôles : toujours tenté, même si le pseudo a échoué au-dessus ---
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
            errors.append("rôles non modifiés (rôle du bot trop bas)")

        if not errors:
            return True, "OK"

        # Rôles appliqués mais pseudo en échec (ou l'inverse) : on considère
        # que c'est un succès partiel, avec le détail de ce qui a raté.
        return True, "Partiel : " + " ; ".join(errors)

    # ------------------------------------------------------------------
    # Callback OAuth (route web)
    # ------------------------------------------------------------------
    async def handle_callback(self, request: web.Request) -> web.Response:
        self._cleanup_expired_logins()

        code = request.query.get("code")
        state = request.query.get("state")
        error = request.query.get("error")

        if error:
            return web.Response(
                text=f"Autorisation refusée ou erreur vAMSYS : {error}. Tu peux fermer cette page.",
                status=400,
            )

        if not code or not state or state not in self.pending_logins:
            return web.Response(
                text="Lien invalide ou expiré. Retourne sur Discord et reclique sur le bouton.",
                status=400,
            )

        login_data = self.pending_logins.pop(state)

        # --- Échange du code contre un token (pas de client_secret : client PKCE public) ---
        async with aiohttp.ClientSession() as session:
            token_payload = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.REDIRECT_URI,
                "client_id": config.VAMSYS_CLIENT_ID,
                "code_verifier": login_data["code_verifier"],
            }

            try:
                async with session.post(config.VAMSYS_TOKEN_URL, data=token_payload) as resp:
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
                async with session.get(config.VAMSYS_PILOT_ME_URL, headers=headers) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        log.error("Échec de récupération du profil pilote (%s) : %s", resp.status, body)
                        return web.Response(
                            text=(
                                "Impossible de récupérer ton profil vAMSYS.\n\n"
                                f"[DEBUG] URL appelée : {config.VAMSYS_PILOT_ME_URL}\n"
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
        guild = self.bot.get_guild(login_data["guild_id"])
        if guild is None:
            return web.Response(text="Le bot ne trouve plus ce serveur Discord.", status=500)

        member = guild.get_member(login_data["discord_user_id"])
        if member is None:
            return web.Response(text="Tu ne sembles plus être membre de ce serveur Discord.", status=400)

        success, message = await self.apply_pilot_to_member(guild, member, pilot_data)

        if success and message == "OK":
            return web.Response(
                text="✅ Compte lié avec succès ! Ton pseudo et ton rôle ont été mis à jour. "
                "Tu peux fermer cette page et retourner sur Discord."
            )
        elif success:
            log.warning("Liaison partielle pour %s : %s", member, message)
            return web.Response(
                text=f"✅ Compte lié, mais avec un avertissement : {message}\n\n"
                "Tu peux fermer cette page. Contacte un administrateur si besoin."
            )
        else:
            log.error("Échec de l'application du pseudo/rôle pour %s : %s", member, message)
            return web.Response(text=f"Connexion réussie, mais erreur côté Discord : {message}", status=500)


async def setup(bot: commands.Bot):
    await bot.add_cog(VamsysCog(bot))