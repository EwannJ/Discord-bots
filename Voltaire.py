import discord
import requests
import os

TOKEN = os.environ.get("VOLTAIRE")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

def correc(txt):
    url = "https://api.languagetool.org/v2/check"
    data = {
        "text": txt,
        "language": "fr"
    }

    reponse = requests.post(url, data=data).json()
    texte_corrige = txt

    for erreur in reversed(reponse["matches"]):
        if erreur["replacements"]:
            debut = erreur["offset"]
            fin = debut + erreur["length"]
            remplacement = erreur["replacements"][0]["value"]
            texte_corrige = texte_corrige[:debut] + remplacement + texte_corrige[fin:]

    return texte_corrige

@client.event
async def on_ready():
    print(f"Voltaire online !")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    texte_original = message.content
    texte_corrige = correc(texte_original)

    if texte_corrige != texte_original:
        await message.reply(
            f"⚠️ Tu as fait une/des faute(s) d'orthographe ! Voici la correction :\n```{texte_corrige}```",
            mention_author=False
        )

client.run(TOKEN)