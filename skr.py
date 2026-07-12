TOKEN = 'MTUyNTkyODE3NjI1MTgzNDYwOA.GER9RR.e13IzvtnrxMKANf8pbZk9jt0lapqzd4FCVUmdw'

import discord
from discord import app_commands
from discord.ext import commands

# On garde les intentions de base
intents = discord.Intents.default()

# On initialise le bot (le préfixe '!' ne servira à rien ici)
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user.name}")
    try:
        # Cette ligne est CRUCIALE : elle envoie la commande /test à Discord
        synced = await bot.tree.sync()
        print(f"Commande Slash synchronisée : {len(synced)} commande(s) prête(s).")
    except Exception as e:
        print(f"Erreur de synchronisation : {e}")

# LA COMMANDE SLASH /test
@bot.tree.command(name="test", description="Tester le bot")
async def test(interaction: discord.Interaction):
    # Le bot répond directement à l'interaction
    await interaction.response.send_message(f"Le bot fonctionne parfaitement en commande Slash ! 🚀")

# Lance le bot avec ton token
bot.run(TOKEN)