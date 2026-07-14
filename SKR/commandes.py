import discord
from discord import app_commands
from discord.ext import commands

import config
from cogs.vamsys import VamsysCog


class LinkAccountView(discord.ui.View):
    """Vue persistante avec le bouton 'Lier mon compte vAMSYS'."""

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

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

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        # Vue persistante : doit être ré-enregistrée à chaque démarrage pour
        # que le bouton reste cliquable après un redémarrage du bot.
        self.bot.add_view(LinkAccountView(self.bot))

# /createrequestbutton
    @app_commands.command(
        name="createrequestbutton",
        description="Crée le bouton de liaison de compte dans ce salon.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create_request_button(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.send(view=LinkAccountView(self.bot))
        await interaction.delete_original_response()

# /ping
    @app_commands.command(name="ping", description="Voir le ping du bot")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"🏓 Pong ! Ma latence est de **{latency}ms**.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(CommandesCog(bot))
