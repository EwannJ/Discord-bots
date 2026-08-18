import discord
from discord import app_commands
from discord.ui import Button, View
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("TSSE")

prise_de_service = {}

adminrole = [1514370877142339744, 1381733917471674459]
idlogs = 1514369143007084654

def get_heure_fr():
    # Force un décalage de +2 heures (UTC+2 pour l'heure d'été française)
    return datetime.now(timezone.utc) + timedelta(hours=2)

class ServiceView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Débuter la session", style=discord.ButtonStyle.green, custom_id="ps_button")
    async def prise_service(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        now = get_heure_fr()
        
        if user.id not in prise_de_service:
            prise_de_service[user.id] = now
        else:
            await interaction.response.send_message("⚠️ Tu as déjà un session d'actif.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Début de session validée !",
            description=f"Tu as débuté ta session à **{now.strftime('%H:%M:%S')}**.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Terminer la session", style=discord.ButtonStyle.red, custom_id="fs_button")
    async def fin_service(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        now = get_heure_fr()
        
        if user.id not in prise_de_service:
            await interaction.response.send_message("⚠️ Tu n'as pas démarré de session. Clique d'abord sur le bouton vert !", ephemeral=True)
            return
            
        heure_ps = prise_de_service[user.id]
        duree = now - heure_ps
        
        secondes_totales = int(duree.total_seconds())
        heures, reste = divmod(secondes_totales, 3600)
        minutes, secondes = divmod(reste, 60)
        duree_formatee = f"{heures}h {minutes}m {secondes}s"
        
        embed_user = discord.Embed(
            title="Fin de session validée !",
            description=f"Session terminée. Durée : **{duree_formatee}**.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed_user, ephemeral=True)
        
        channel_logs = interaction.guild.get_channel(idlogs)
        if channel_logs:
            embed_log = discord.Embed(
                title="📊 Rapport de session",
                color=discord.Color.blue(),
                timestamp=get_heure_fr()
            )
            # FIX : Remplacement de la variable manquante mention_membre par user.mention
            embed_log.add_field(name="🛠️ Développeur", value=user.mention, inline=False)
            embed_log.add_field(name="🟢 Début session", value=heure_ps.strftime('%d/%m/%Y à %H:%M:%S'), inline=True)
            embed_log.add_field(name="🔴 Fin session", value=now.strftime('%d/%m/%Y à %H:%M:%S'), inline=True)
            embed_log.add_field(name="⏱️ Durée totale", value=f"**{duree_formatee}**", inline=False)
            
            await channel_logs.send(embed=embed_log)
            
        del prise_de_service[user.id]


class MonBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True # Activé pour pouvoir chercher les membres correctement
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f'TSSE online !')
        try:
            self.add_view(ServiceView())
            synced = await self.tree.sync()
            print(f"Synchronisé {len(synced)} commande(s).")
        except Exception as e:
            print(e)

bot = MonBot()

# Commande /setup
@bot.tree.command(name="setup", description="Installe l'embed de prise/fin de session")
async def setup(interaction: discord.Interaction):
    # Vérification si l'utilisateur possède au moins un des rôles de la liste adminrole
    if not any(role.id in adminrole for role in interaction.user.roles):
        await interaction.response.send_message("❌ Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📝 Pointage de l'équipe développement",
        description="Cliquez sur les boutons ci-dessous pour gérer votre temps de session.\n\n"
                    "🟢 **Débuter la session** : Commencer votre session de développement.\n"
                    "🔴 **Terminer la session** : Terminer la session et envoyer le rapport.",
        color=discord.Color.blurple()
    )
    
    await interaction.response.send_message("Menu de pointage configuré !", ephemeral=True)
    await interaction.channel.send(embed=embed, view=ServiceView())

# Commande /forceps
@bot.tree.command(name="forceps", description="Force le début d'une session d'un développeur.")
@app_commands.describe(membre="Le développeur à mettre en service")
async def force_ps(interaction: discord.Interaction, membre: discord.Member):
    if not any(role.id in adminrole for role in interaction.user.roles):
        await interaction.response.send_message("❌ Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
        return

    if membre.id in prise_de_service:
        await interaction.response.send_message(f"❌ {membre.mention} a déjà débuté une session.", ephemeral=True)
        return

    now = get_heure_fr()
    prise_de_service[membre.id] = now

    await interaction.response.send_message(
        f"✅ Début de session forcée pour {membre.mention} à **{now.strftime('%H:%M:%S')}**.", 
        ephemeral=True
    )

# Commande /forcenewps
@bot.tree.command(name="forcenewps", description="Force le début d'une nouvelle session d'un développeur.")
@app_commands.describe(membre="Le développeur à mettre en service")
async def forcenew_ps(interaction: discord.Interaction, membre: discord.Member):
    if not any(role.id in adminrole for role in interaction.user.roles):
        await interaction.response.send_message("❌ Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
        return

    now = get_heure_fr()
    prise_de_service[membre.id] = now

    await interaction.response.send_message(
        f"✅ Début de session forcée pour {membre.mention} à **{now.strftime('%H:%M:%S')}**.", 
        ephemeral=True
    )

# Commande /forcefs
@bot.tree.command(name="forcefs", description="Force la fin de la session d'un développeur.")
@app_commands.describe(
    membre="Le développeur à sortir de sa session.",
    enregistrer="Enregistrer la session dans les logs ? (Oui par défaut)"
)
@app_commands.choices(enregistrer=[
    app_commands.Choice(name="Oui", value=1),
    app_commands.Choice(name="Non", value=0)
])
async def force_fs(interaction: discord.Interaction, membre: discord.Member, enregistrer: int = 1):
    if not any(role.id in adminrole for role in interaction.user.roles):
        await interaction.response.send_message("❌ Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
        return

    if membre.id not in prise_de_service:
        await interaction.response.send_message(f"❌ {membre.mention} n'a pas débuté de session actuellement.", ephemeral=True)
        return

    now = get_heure_fr()
    heure_ps = prise_de_service[membre.id]
    
    duree = now - heure_ps
    secondes_totales = int(duree.total_seconds())
    heures, reste = divmod(secondes_totales, 3600)
    minutes, secondes = divmod(reste, 60)
    duree_formatee = f"{heures}h {minutes}m {secondes}s"

    if enregistrer == 1:
        await interaction.response.send_message(
            f"✅ Fin de session forcée pour {membre.mention}. Durée : **{duree_formatee}**.", 
            ephemeral=True
        )

        channel_logs = interaction.guild.get_channel(idlogs)
        if channel_logs:
            embed_log = discord.Embed(
                title="📊 Rapport de session",
                color=discord.Color.blue(),
                timestamp=get_heure_fr()
            )
            # FIX : Remplacement de la variable manquante mention_membre par membre.mention
            embed_log.add_field(name="🛠️ Développeur", value=membre.mention, inline=False)
            embed_log.add_field(name="🟢 Début session", value=heure_ps.strftime('%d/%m/%Y à %H:%M:%S'), inline=True)
            embed_log.add_field(name="🔴 Fin session", value=now.strftime('%d/%m/%Y à %H:%M:%S'), inline=True)
            embed_log.add_field(name="⏱️ Durée totale", value=f"**{duree_formatee}**", inline=False)
                
            await channel_logs.send(embed=embed_log)
    else:
        await interaction.response.send_message(
            f"🗑️ Fin de session forcée pour {membre.mention} **sans enregistrement** (Session annulée).", 
            ephemeral=True
        )
            
    del prise_de_service[membre.id]

# Commande /ensession
@bot.tree.command(name="ensession", description="Affiche la liste des développeurs actuellement en session")
async def en_service(interaction: discord.Interaction):
    if not any(role.id in adminrole for role in interaction.user.roles):
        await interaction.response.send_message("❌ Tu n'as pas la permission.", ephemeral=True)
        return

    if not prise_de_service:
        embed_vide = discord.Embed(
            title="🛠️ Développeurs en session",
            description="Personne n'est en session actuellement.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed_vide, ephemeral=True)
        return

    embed_liste = discord.Embed(
        title="🛠️ Développeurs actuellement en session",
        color=discord.Color.green(),
        timestamp=get_heure_fr()
    )
    
    texte_membres = ""
    now = get_heure_fr()

    for user_id, heure_ps in prise_de_service.items():
        membre = interaction.guild.get_member(user_id)
        if not membre:
            try:
                membre = await interaction.guild.fetch_member(user_id)
            except discord.NotFound:
                membre = None

        mention_membre = membre.mention if membre else f"Utilisateur inconnu ({user_id})"
        
        duree = now - heure_ps
        secondes_totales = int(duree.total_seconds())
        heures, reste = divmod(secondes_totales, 3600)
        minutes, secondes = divmod(reste, 60)
        duree_formatee = f"{heures}h {minutes}m {secondes}s"
        
        texte_membres += f"• {mention_membre} — En session depuis **{heure_ps.strftime('%H:%M:%S')}** (soit ⏱️ **{duree_formatee}**)\n"

    embed_liste.description = texte_membres
    embed_liste.set_footer(text=f"Total : {len(prise_de_service)} personne(s) active(s)")
    await interaction.response.send_message(embed=embed_liste, ephemeral=True)

# Commande /setsession
@bot.tree.command(name="setsession", description="Enregistre manuellement une session passée pour un développeur")
@app_commands.describe(
    membre="Le développeur concerné",
    debut="Format: DD/MM/AAAA HH:MM (Ex: 11/06/2026 14:30)",
    fin="Format: DD/MM/AAAA HH:MM (Ex: 11/06/2026 17:45)"
)
async def set_service(interaction: discord.Interaction, membre: discord.Member, debut: str, fin: str):
    if not any(role.id in adminrole for role in interaction.user.roles):
        await interaction.response.send_message("❌ Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
        return

    try:
        format_date = "%d/%m/%Y %H:%M"
        date_debut = datetime.strptime(debut, format_date)
        date_fin = datetime.strptime(fin, format_date)
    except ValueError:
        await interaction.response.send_message(
            "❌ Format de date incorrect. Utilise bien le format `JJ/MM/AAAA HH:MM`\n*Exemple : 11/06/2026 14:30*", 
            ephemeral=True
        )
        return

    if date_fin <= date_debut:
        await interaction.response.send_message("❌ La date de fin doit être située après la date de début !", ephemeral=True)
        return

    duree = date_fin - date_debut
    secondes_totales = int(duree.total_seconds())
    heures, reste = divmod(secondes_totales, 3600)
    minutes, secondes = divmod(reste, 60)
    duree_formatee = f"{heures}h {minutes}m {secondes}s"

    await interaction.response.send_message(
        f"✅ Session manuelle enregistrée pour {membre.mention}. Durée : **{duree_formatee}**.", 
        ephemeral=True
    )

    channel_logs = interaction.guild.get_channel(idlogs)
    if channel_logs:
        embed_log = discord.Embed(
            title="📊 Rapport de session",
            color=discord.Color.blue(),
            timestamp=get_heure_fr()
        )
        
        # FIX : Remplacement des variables incorrectes par les dates saisies par l'admin
        embed_log.add_field(name="🛠️ Développeur", value=membre.mention, inline=False)
        embed_log.add_field(name="🟢 Début session", value=date_debut.strftime('%d/%m/%Y à %H:%M:%S'), inline=True)
        embed_log.add_field(name="🔴 Fin session", value=date_fin.strftime('%d/%m/%Y à %H:%M:%S'), inline=True)
        embed_log.add_field(name="⏱️ Durée totale", value=f"**{duree_formatee}**", inline=False)
            
        await channel_logs.send(embed=embed_log)

# Commande /forcefsall
@bot.tree.command(name="forcefsall", description="Force la fin de la session de TOUS les développeurs actifs.")
@app_commands.describe(enregistrer="Enregistrer les sessions de tout le monde dans les logs ? (Oui par défaut)")
@app_commands.choices(enregistrer=[
    app_commands.Choice(name="Oui", value=1),
    app_commands.Choice(name="Non", value=0)
])
async def force_fs_all(interaction: discord.Interaction, enregistrer: int = 1):
    if not any(role.id in adminrole for role in interaction.user.roles):
        await interaction.response.send_message("❌ Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
        return

    if not prise_de_service:
        await interaction.response.send_message("⚠️ Aucun développeur n'est actuellement en session.", ephemeral=True)
        return

    now = get_heure_fr()
    nb_membres = len(prise_de_service)
    channel_logs = interaction.guild.get_channel(idlogs)
    liste_utilisateurs = list(prise_de_service.items())

    for user_id, heure_ps in liste_utilisateurs:
        if enregistrer == 1 and channel_logs:
            duree = now - heure_ps
            secondes_totales = int(duree.total_seconds())
            heures, reste = divmod(secondes_totales, 3600)
            minutes, secondes = divmod(reste, 60)
            duree_formatee = f"{heures}h {minutes}m {secondes}s"

            membre = interaction.guild.get_member(user_id)
            if not membre:
                try:
                    membre = await interaction.guild.fetch_member(user_id)
                except discord.NotFound:
                    membre = None

            mention_membre = membre.mention if membre else f"Utilisateur inconnu ({user_id})"

            embed_log = discord.Embed(
                title="📊 Rapport de session",
                color=discord.Color.blue(),
                timestamp=get_heure_fr()
            )
            embed_log.add_field(name="🛠️ Développeur", value=mention_membre, inline=False)
            embed_log.add_field(name="🟢 Début session", value=heure_ps.strftime('%d/%m/%Y à %H:%M:%S'), inline=True)
            embed_log.add_field(name="🔴 Fin session", value=now.strftime('%d/%m/%Y à %H:%M:%S'), inline=True)
            embed_log.add_field(name="⏱️ Durée totale", value=f"**{duree_formatee}**", inline=False)
            
            await channel_logs.send(embed=embed_log)

    prise_de_service.clear()
    statut_enregistrement = "avec enregistrement des logs" if enregistrer == 1 else "SANS enregistrement"
    await interaction.response.send_message(
        f"✅ Fin de session générale validée pour les **{nb_membres}** développeur(s) actif(s) ({statut_enregistrement}).", 
        ephemeral=True
    )

# Pagination /historique
class HistoriquePagination(discord.ui.View):
    def __init__(self, embed_base, pages, membre_name, debut, fin):
        super().__init__(timeout=60)
        self.embed_base = embed_base
        self.pages = pages
        self.current_page = 0
        self.membre_name = membre_name
        self.debut = debut
        self.fin = fin
        self.update_buttons()

    def update_buttons(self):
        self.prev_page.disabled = self.current_page == 0 # type: ignore
        self.next_page.disabled = self.current_page == len(self.pages) - 1 # type: ignore

    def create_embed(self):
        embed = self.embed_base.copy()
        embed.title = f"📋 Historique — {self.membre_name} (Page {self.current_page + 1}/{len(self.pages)})"
        embed.clear_fields()
        embed.add_field(name="🔗 Liste des sessions (Redirections)", value=self.pages[self.current_page], inline=False)
        return embed

    @discord.ui.button(label="◀ Précédent", style=discord.ButtonStyle.blurple, custom_id="prev_hist")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Suivant ▶", style=discord.ButtonStyle.blurple, custom_id="next_hist")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

# Commande /historique
@bot.tree.command(name="historique", description="Calcule le temps de développement total d'un développeur sur un temps donné")
@app_commands.describe(
    membre="Le développeur dont on veut l'historique",
    debut="Format: DD/MM/AAAA (Ex: 01/06/2026)",
    fin="Format: DD/MM/AAAA (Ex: 11/06/2026)",
    afficher_details="Afficher la liste détaillée avec les liens vers chaque log ? (Oui par défaut)"
)
@app_commands.choices(afficher_details=[
    app_commands.Choice(name="Oui", value=1),
    app_commands.Choice(name="Non", value=0)
])
async def historique(interaction: discord.Interaction, membre: discord.Member, debut: str, fin: str, afficher_details: int = 1):
    if not any(role.id in adminrole for role in interaction.user.roles):
        await interaction.response.send_message("❌ Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
        return

    try:
        format_date = "%d/%m/%Y"
        date_debut = datetime.strptime(debut, format_date)
        date_fin = datetime.strptime(fin, format_date).replace(hour=23, minute=59, second=59)
    except ValueError:
        await interaction.response.send_message("❌ Format de date incorrect. Utilise le format `JJ/MM/AAAA`", ephemeral=True)
        return

    if date_fin < date_debut:
        await interaction.response.send_message("❌ La date de fin doit être après la date de début !", ephemeral=True)
        return

    channel_logs = interaction.guild.get_channel(idlogs)
    if not channel_logs:
        await interaction.response.send_message("❌ Le salon des logs est introuvable.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    total_secondes = 0
    sessions_trouvees = 0
    liste_lignes = []

    async for message in channel_logs.history(limit=500):
        if message.embeds:
            msg_date = message.created_at.replace(tzinfo=None)
            if date_debut <= msg_date <= date_fin:
                embed = message.embeds[0]
                if embed.title and "Rapport de session" in embed.title:
                    is_target = False
                    duree_string = ""
                    
                    for field in embed.fields:
                        if field.name == "🛠️ Développeur" and membre.mention in field.value:
                            is_target = True
                        elif field.name == "⏱️ Durée totale":
                            duree_string = field.value

                    if is_target and duree_string:
                        try:
                            clean_str = duree_string.replace("⏱️", "").replace("**", "").strip()
                            parts = clean_str.split()
                            h, m, s = 0, 0, 0
                            for part in parts:
                                if 'h' in part: h = int(part.replace('h', ''))
                                elif 'm' in part: m = int(part.replace('m', ''))
                                elif 's' in part: s = int(part.replace('s', ''))
                            
                            total_secondes += (h * 3600) + (m * 60) + s
                            sessions_trouvees += 1
                            
                            if afficher_details == 1:
                                liste_lignes.append(f"• Session du {msg_date.strftime('%d/%m/%Y')} : **{clean_str}** → [Voir le log]({message.jump_url})")
                        except Exception:
                            continue

    heures, reste = divmod(total_secondes, 3600)
    minutes, secondes = divmod(reste, 60)
    total_formate = f"{heures}h {minutes}m {secondes}s"

    embed_base = discord.Embed(
        description=f"Statistiques des sessions demandées du **{debut}** au **{fin}**.\n\n"
                    f"📊 Sessions trouvées : **{sessions_trouvees}**\n"
                    f"⏱️ Temps de travail total : **{total_formate}**",
        color=discord.Color.blurple()
    )

    if afficher_details == 1 and liste_lignes:
        pages = ["\n".join(liste_lignes[i:i+5]) for i in range(0, len(liste_lignes), 5)]
        view = HistoriquePagination(embed_base, pages, membre.display_name, debut, fin)
        await interaction.followup.send(embed=view.create_embed(), view=view, ephemeral=True)
    else:
        embed_base.title = f"📋 Historique — {membre.display_name}"
        await interaction.followup.send(embed=embed_base, ephemeral=True)

# Pagination /historiqueall
class AllHistoriquePagination(discord.ui.View):
    def __init__(self, embed_base, pages):
        super().__init__(timeout=60)
        self.embed_base = embed_base
        self.pages = pages
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.prev_page.disabled = self.current_page == 0 # type: ignore
        self.next_page.disabled = self.current_page == len(self.pages) - 1 # type: ignore

    def create_embed(self):
        embed = self.embed_base.copy()
        embed.title = f"📋 Classement & Historique Global (Page {self.current_page + 1}/{len(self.pages)})"
        embed.clear_fields()
        embed.add_field(name="🔗 Redirections de toutes les sessions", value=self.pages[self.current_page], inline=False)
        return embed

    @discord.ui.button(label="◀ Précédent", style=discord.ButtonStyle.green, custom_id="all_prev")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Suivant ▶", style=discord.ButtonStyle.green, custom_id="all_next")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

# Commande /historiqueall
@bot.tree.command(name="historiqueall", description="Affiche le temps de développement total de tous les développeurs.")
@app_commands.describe(
    debut="Format: DD/MM/AAAA (Ex: 01/06/2026)",
    fin="Format: DD/MM/AAAA (Ex: 11/06/2026)",
    afficher_details="Afficher la liste détaillée avec les liens vers chaque log ? (Oui par défaut)"
)
@app_commands.choices(afficher_details=[
    app_commands.Choice(name="Oui", value=1),
    app_commands.Choice(name="Non", value=0)
])
async def all_historique(interaction: discord.Interaction, debut: str, fin: str, afficher_details: int = 1):
    if not any(role.id in adminrole for role in interaction.user.roles):
        await interaction.response.send_message("❌ Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
        return

    try:
        format_date = "%d/%m/%Y"
        date_debut = datetime.strptime(debut, format_date)
        date_fin = datetime.strptime(fin, format_date).replace(hour=23, minute=59, second=59)
    except ValueError:
        await interaction.response.send_message("❌ Format de date incorrect. Utilise le format `JJ/MM/AAAA`.", ephemeral=True)
        return

    if date_fin < date_debut:
        await interaction.response.send_message("❌ La date de fin doit être après la date de début !", ephemeral=True)
        return

    channel_logs = interaction.guild.get_channel(idlogs)
    if not channel_logs:
        await interaction.response.send_message("❌ Le salon des logs est introuvable.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    stats_globale = {}
    liste_lignes = []

    async for message in channel_logs.history(limit=500):
        if message.embeds:
            msg_date = message.created_at.replace(tzinfo=None)
            if date_debut <= msg_date <= date_fin:
                embed = message.embeds[0]
                if embed.title and "Rapport de session" in embed.title:
                    dev_mention = None
                    duree_string = ""
                    
                    for field in embed.fields:
                        if field.name == "🛠️ Développeur":
                            dev_mention = field.value
                        elif field.name == "⏱️ Durée totale":
                            duree_string = field.value

                    if dev_mention and duree_string:
                        try:
                            clean_str = duree_string.replace("⏱️", "").replace("**", "").strip()
                            parts = clean_str.split()
                            h, m, s = 0, 0, 0
                            for part in parts:
                                if 'h' in part: h = int(part.replace('h', ''))
                                elif 'm' in part: m = int(part.replace('m', ''))
                                elif 's' in part: s = int(part.replace('s', ''))
                            
                            secondes_session = (h * 3600) + (m * 60) + s
                            
                            if dev_mention in stats_globale:
                                stats_globale[dev_mention] += secondes_session
                            else:
                                stats_globale[dev_mention] = secondes_session
                                
                            if afficher_details == 1:
                                liste_lignes.append(f"• {dev_mention} ({msg_date.strftime('%d/%m')} : **{clean_str}**) → [Voir le log]({message.jump_url})")
                        except Exception:
                            continue

    embed_base = discord.Embed(
        description=f"Statistiques de l'équipe du **{debut}** au **{fin}**.\n\n",
        color=discord.Color.green()
    )

    if not stats_globale:
        embed_base.description += "⚠️ Aucune session de développement enregistrée sur cette période."
        embed_base.title = "📋 Classement & Historique Global"
        await interaction.followup.send(embed=embed_base, ephemeral=True)
        return

    texte_resultat = ""
    stats_triees = sorted(stats_globale.items(), key=lambda item: item[1], reverse=True)
    
    for index, (dev, total_sec) in enumerate(stats_triees, start=1):
        heures, reste = divmod(total_sec, 3600)
        minutes, secondes = divmod(reste, 60)
        total_formate = f"{heures}h {minutes}m {secondes}s"
        texte_resultat += f"#{index} {dev} — ⏱️ **{total_formate}**\n"
    
    embed_base.description += texte_resultat

    if afficher_details == 1 and liste_lignes:
        pages = ["\n".join(liste_lignes[i:i+5]) for i in range(0, len(liste_lignes), 5)]
        view = AllHistoriquePagination(embed_base, pages)
        await interaction.followup.send(embed=view.create_embed(), view=view, ephemeral=True)
    else:
        embed_base.title = "📋 Classement & Historique Global"
        await interaction.followup.send(embed=embed_base, ephemeral=True)

# Lancement du bot
bot.run(TOKEN)