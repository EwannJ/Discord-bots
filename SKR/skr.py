import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands

load_dotenv()
TOKEN = os.getenv('TOKEN')

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents, help_command=None)

@bot.tree.command(name="ping", description="Voir le ping du bot")
@app_commands.checks.has_permissions(manage_messages=True)
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong ! Ma latence est de **{latency}ms**.", ephemeral=True)

@bot.event
async def on_ready():
    print("SKR online !")
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} commandes syncronisées")
    except Exception as e:
        print(f"⚠️ Erreur lors de la synchronisation des commandes : {e}")

bot.run(TOKEN)