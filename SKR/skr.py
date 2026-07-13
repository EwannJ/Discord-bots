import discord
from discord import app_commands

TOKEN = 'MTUyNTkyODE3NjI1MTgzNDYwOA.GER9RR.e13IzvtnrxMKANf8pbZk9jt0lapqzd4FCVUmdw'

client = discord.Client(intents=discord.Intents.all())

@app_commands.command(name="test", description="Test des commandes")
@app_commands.describe(
    Test1="Texte",
    Test2="Choix"
)
@app_commands.choices(Test2=[
    app_commands.Choice(name="Choix 1"),
    app_commands.Choice(name="Choix 2")
])
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.guild_only()
async def rrnote(interaction: discord.Interaction)
    await fo


@client.event
async def on_ready():
    print("SKR online !")

client.run(TOKEN)