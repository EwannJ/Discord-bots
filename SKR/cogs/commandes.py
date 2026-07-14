import logging

import discord
from discord import app_commands
from discord.ext import commands

import config
from cogs.vamsys import VamsysCog

log = logging.getLogger("skr_bot.commandes")


def _format_record(record: dict, member: discord.Member) -> discord.Embed:
    embed = discord.Embed(title="Compte lié", color=discord.Color.blurple())
    embed.add_field(name="ID SKR", value=record.get("skr_id") or "—", inline=True)
    full_name = f"{record.get('first_name') or ''} {record.get('last_name') or ''}".strip()
    embed.add_field(name="Nom", value=full_name or "—", inline=True)
    embed.add_field(name="Discord", value=member.mention, inline=False)
    embed.add_field(name="Lié le", value=record.get("linked_at") or "—", inline=False)
    return embed


class LinkAccountView(discord.ui.View):
    """Vue persistante avec le bouton 'Lier mon compte vAMSYS'."""

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        # Sans ça, une erreur inattendue (ex: vAMSYS injoignable, cog non
        # chargé, etc.) fait juste échouer l'interaction côté Discord sans
        # rien logger — impossible à diagnostiquer. On log ET on prévient
        # l'utilisateur au lieu de le laisser avec "Cette interaction a échoué".
        log.exception("Erreur dans le bouton de liaison vAMSYS : %s", error)
        message = (
            "Une erreur inattendue est survenue. Réessaie dans quelques instants, "
            "et préviens un administrateur si ça persiste."
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            pass

    @discord.ui.button(
        label="Lier mon compte vAMSYS",
        style=discord.ButtonStyle.primary,
        custom_id="link-vamsys-account",
    )
    async def link_account(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.guild_id) not in config.SERVERS:
            await interaction.response.send_message(
                "Ce serveur n'est pas configuré correctement. Contactez un administrateur.",
                ephemeral=True,
            )
            return

        vamsys_cog: VamsysCog = self.bot.get_cog("VamsysCog")
        if vamsys_cog is None:
            await interaction.response.send_message(
                "Le module vAMSYS n'est pas chargé. Contactez un administrateur.",
                ephemeral=True,
            )
            return

        state, code_challenge = vamsys_cog.create_pending_login(
            interaction.user.id, interaction.guild_id
        )
        authorize_url = vamsys_cog.build_authorize_url(state, code_challenge)

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


class CommandesCog(commands.Cog):
    """Slash commands du bot : bouton de liaison, ping, etc."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        # Vue persistante : doit être ré-enregistrée à chaque démarrage pour
        # que le bouton reste cliquable après un redémarrage du bot.
        self.bot.add_view(LinkAccountView(self.bot))

    @app_commands.command(
        name="createrequestbutton",
        description="Crée le bouton de liaison de compte dans ce salon.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create_request_button(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.send(view=LinkAccountView(self.bot))
        await interaction.delete_original_response()

    @app_commands.command(name="ping", description="Voir le ping du bot")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"🏓 Pong ! Ma latence est de **{latency}ms**.", ephemeral=True
        )

    @app_commands.command(
        name="account",
        description="Affiche les infos du compte vAMSYS lié à un membre.",
    )
    @app_commands.describe(membre="Le membre Discord à consulter")
    @app_commands.checks.has_permissions(manage_permissions=True)
    async def account(self, interaction: discord.Interaction, membre: discord.Member):
        await interaction.response.defer(ephemeral=True)

        record = await self.bot.supabase.get_by_discord_id(str(membre.id))

        if record is None:
            await interaction.followup.send(
                f"Aucun compte lié trouvé pour {membre.mention}.", ephemeral=True
            )
            return

        await interaction.followup.send(embed=_format_record(record, membre), ephemeral=True)

    @app_commands.command(
        name="removeaccount",
        description="Supprime l'entrée de liaison d'un membre.",
    )
    @app_commands.describe(membre="Le membre Discord dont il faut supprimer la liaison")
    @app_commands.checks.has_permissions(manage_permissions=True)
    async def remove_account(self, interaction: discord.Interaction, membre: discord.Member):
        await interaction.response.defer(ephemeral=True)

        record = await self.bot.supabase.get_by_discord_id(str(membre.id))
        if record is None:
            await interaction.followup.send(
                f"Aucun compte lié trouvé pour {membre.mention}.", ephemeral=True
            )
            return

        deleted = await self.bot.supabase.delete(str(membre.id))

        if deleted:
            await interaction.followup.send(
                f"✅ Entrée supprimée pour {membre.mention} (`{record.get('skr_id') or '?'}`). "
                "Le pseudo/rôle Discord actuels ne sont pas modifiés automatiquement.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "❌ Erreur lors de la suppression en base.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(CommandesCog(bot))