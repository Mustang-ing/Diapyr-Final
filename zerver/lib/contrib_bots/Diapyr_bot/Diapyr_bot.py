import json
import os
import statistics
import sys

import sys
# Set the settings module from your Zulip settings (adjust path if needed)
sys.path.append("/home/ghostie/Diapyr/Diapyr-Final")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")

import django
django.setup()

import zulip
import random
from datetime import datetime, timedelta, timezone
import time
import threading
from zerver.models.debat import Debat,Participant
import random
import math
from typing import Dict, List, Set
from bs4 import BeautifulSoup
# Configuration du bot
client = None
# Statistiques pour voir le nb de msg/caracteres envoyés:
stats_utilisateurs = {}  # email → {"messages": 0, "caracteres": 0}
messages_consecutifs = {"last_sender": None, "count": 0}
# Pour le suivi des alertes de participation faible
dernier_alerte_utilisateur = {}  # email → datetime de la dernière alerte
COOLDOWN_ALERTES = 300  # 5mins entre deux alertes pour le même utilisateur
#pour laffichage des stat
id_message_stats = None  # contiendra l'ID du message à mettre à jour
stream_stats = None  # contiendra le nom du stream où poster les stats

def get_client() -> None:
    #Initialise le client Zulip.
    global client
    if client is None:
        client = zulip.Client(config_file="zerver/lib/contrib_bots/Diapyr_bot/zuliprc.txt")
        print("Client Zulip initialisé avec succès !")
    return client

class ObjectD:
    def __init__(self, name: str , creator_email: str , max_per_group: str , end_date: datetime, time_between_steps: timedelta, num_pass: int) -> None:
        self.name = name
        self.creator_email = creator_email
        self.max_per_group = max_per_group
        self.end_date = end_date
        self.time_between_steps = time_between_steps if isinstance(time_between_steps, timedelta) else timedelta(seconds=int(time_between_steps))
        #Il pourrait être intéressant de ettre un contrôle sur la valeur du time between_step 
        self.num_pass = num_pass
        self.step = 1
        self.subscribers = {}
        self.channels_created = False
        # Structures pour gérer les sondages
        self.selected: list[str] = []           # [emails]
        self.group_members: Dict[str, List[str]] = {}  # {stream_name: [emails]}

        print(f"Création d'un objet débat : {name}")

    def add_subscriber(self, user_email: str , user_info: dict[str, str]) -> None:
        #Ajoute un utilisateur à la liste des inscrits.
        self.subscribers[user_email] = user_info
        print(f"Ajout du participant {user_email}")

    def split_into_groups(self) -> list[list[str]]:
        print("Répartition des utilisateurs en groupes...")
        users = list(self.subscribers.keys())
        if self.creator_email in users:
            users.remove(self.creator_email)
        random.shuffle(users)
        groups = [users[i:i + self.max_per_group] for i in range(0, len(users), self.max_per_group)]
        for group in groups:
            group.append(self.creator_email)  # Ajout fictif du créateur
        return groups
    
    def create_streams_for_groups(self, groups: list[list[str]]) -> list[str]:
        #Crée des streams pour chaque groupe et ajoute les utilisateurs.
        print("Ajout des utilisateurs dans les streams existants...")
        streams = []
        for i, group in enumerate(groups):
            stream_name = self.name + self.step * "I" + f"{i+1}" #Changer le nom pour plus de clarté
            print(f"Tentative d'ajout dans le stream : {stream_name}")
            if add_users_to_stream(stream_name, group):
                notify_users(stream_name, group)
                streams.append(stream_name)
        return streams

    def next_step(self) -> bool:
        print("Passage à l'étape suivante...")
        users = list(self.subscribers.keys())
        if len(users) <= self.max_per_group:
            return False
        selected_users = random.sample(users, min(self.num_pass * (len(users) // self.max_per_group), len(users)))
        self.subscribers = {user: self.subscribers[user] for user in selected_users}
        self.step += 1
        return True

    def get_status(self) -> str:
        users = list(self.subscribers.keys())
        print("gagagaaaaaaaaaaaaaaaaa")

        if self.creator_email not in users:
            users.append(self.creator_email)
        groups = [users[i:i + self.max_per_group] for i in range(0, len(users), self.max_per_group)]
        for group in groups:
            group.append(self.creator_email)
        info = f"Nom: {self.name}\nÉtape: {self.step}\nFin inscription: {self.end_date}\nTemps entre étapes: {self.time_between_steps}\nNb à sélectionner: {self.num_pass}\n"
        info += f"Nombre de groupes: {len(groups)}\n"
        for idx, group in enumerate(groups):
            info += f"Groupe {idx + 1}: {', '.join(group)}\n"
        return info

    
    # Méthode  pour envoyer une question d'enquette pour tous les participants

    def send_enquette(self, group_members: list[str]) -> None:
        for member in group_members:
            try:
                result = client.send_message({
                    "type": "private",
                    "to": member,
                    "content": "Voulez-vous participer aux étapes suivantes? (oui/non)",
                })
                print(f"Message envoyé à {member}: {result}")
            except Exception as e:
                print(f"Erreur lors de l'envoi à {member}: {e}")


        # fonction pour envoyer sondage final

    def send_final_poll(self, stream_name: str, candidates: List[str]) -> Set[str]:
        """Send final poll and process votes allowing multiple votes per member."""
        if stream_name not in self.group_members:
            print(f"Unknown stream: {stream_name}")
            return set()

        group = self.group_members[stream_name]
        if not group or not candidates:
            print(f"No valid candidates in {stream_name}")
            return set()

        # Get member names
        try:
            all_members = client.get_members()["members"]
            email_to_name = {m["email"]: m["full_name"] for m in all_members}
        except Exception as e:
            print(f"Error getting members: {e}")
            return set()

        # Filter valid candidates
        valid_candidates = [c for c in candidates if c in group and c in email_to_name]
        if not valid_candidates:
            print(f"No valid candidates in {stream_name}")
            return set()

        # Create multi-choice poll
        question = f"Vote final: Sélectionnez jusqu'à {self.max_per_group} membres pour l'étape suivante"
        options = [f'"{email_to_name[c]}"' for c in valid_candidates]
        poll_command = f'/poll "{question}" {" ".join(options)}'
        
        try:
            response = client.send_message({
                "type": "stream",
                "to": stream_name,
                "subject": "Sondage final",
                "content": poll_command + " --multiple"
            })
            print(f"Multi-choice poll sent to {stream_name}")
        except Exception as e:
            print(f"Error sending poll: {e}")
            return set()

        # Wait for votes (simulated)
        time.sleep(120)  # Wait 2 minutes for votes
        
        # Simulate realistic voting (each member votes for multiple candidates)
        vote_count = {c: 0 for c in valid_candidates}
        voters = [m for m in group ]  
        
        for voter in voters:
            try:
                # Number of votes this member will cast (1 to max_per_group)
                num_votes = random.randint(1, self.max_per_group)
                
                # Select distinct candidates to vote for
                voted_for = random.sample(valid_candidates, min(num_votes, len(valid_candidates)))
                
                for candidate in voted_for:
                    vote_count[candidate] += 1
            except Exception as e:
                print(f"Error simulating vote: {e}")

        # Calculate threshold (2/3 of voters)
        threshold = math.ceil(len(voters) * (2 / 3))
        selected = {email for email, count in vote_count.items() if count >= threshold}
        
        print(f"Vote results for {stream_name}: {vote_count}")
        print(f"Threshold: {threshold}, Selected: {selected}")
        return selected



    # fonction pour récuperer les réponses issue des messages privés

    def collect_reponses(self, stream_name: str) -> list[str]:
        self.selected = []
        members = self.group_members.get(stream_name, [])
        
        if not members:
            print(f"No members found for stream {stream_name}")
            return self.selected

        for member in members:
            try:
                # Fetch the most recent message in the PM conversation
                request = {
                    "anchor": "newest",
                    "num_before": 1,  # Get only the most recent message
                    "num_after": 0,
                    "narrow": [
                        {"operator": "pm-with", "operand": member},
                    ],
                }
                
                response = client.get_messages(request)
                
                if not response.get("result") == "success":
                    print(f"Failed to fetch messages for {member}: {response.get('msg', 'Unknown error')}")
                    continue
                    
                messages = response.get("messages", [])
                
                if not messages:
                    print(f"pas de message trouvé {member}")
                    continue
                    
                # Get the most recent message
                last_message = messages[0]
                content = last_message.get("content", "")
                
                # Parse HTML and clean text
                content_text = BeautifulSoup(content, "html.parser").get_text().strip().lower()
                
                # Check if the message is a response to our poll
                if content_text == "oui":
                    print(f"réponse positif de {member}")
                    self.selected.append(member)
                    
            except Exception as e:
                print(f"Error processing response from {member}: {str(e)}")
                continue
                
        print(f"Collected responses for {stream_name}: {self.selected}")
        return self.selected



    # fonction pour commencer le debat

    def start_debate_process(self) -> None:

        def run_steps() -> None:

            try:
                while True:
                    # Attente entre étapes
                    total_seconds = int(self.time_between_steps.total_seconds())
                    print(f"\n---\nAttente de {self.time_between_steps} avant étape {self.step}...")
                    time.sleep(total_seconds)

                    print(f"\n=== Début étape {self.step} du débat '{self.name}' ===")

                    # 1. Création des groupes
                    groups = self.split_into_groups()
                    if not groups:
                        print("Aucun groupe créé, fin du débat")
                        break

                    stream_names = []
                    for i, group in enumerate(groups):
                        stream_name = f"{self.name}{'I' * self.step}{i + 1}"
                        stream_names.append(stream_name)
                        self.group_members[stream_name] = group

                    # 2. Envoi des MPs
                    for stream_name in stream_names:
                        self.send_enquette(self.group_members[stream_name])
                    print(f"envoie enquette...")

                    # 3. Attente des réponses
                    print("\nEn attente des réponses à l'enquétte...")
                    time.sleep(120) 

                    # 4. Traitement des réponses
                    selected_members = set()
                    for stream_name in stream_names:
                        responders = self.collect_reponses(stream_name)
                        if responders:
                            selected = self.send_final_poll(stream_name, responders)
                            selected_members.update(selected)
                    # 5. Préparation étape suivante
                    if not selected_members:
                        print("Aucun membre sélectionné, fin du débat")
                        break

                    # Mise à jour des participants
                    self.subscribers = {
                        email: info 
                        for email, info in self.subscribers.items() 
                        if email in selected_members
                    }
                    self.step += 1

                    # Vérifier si fin du débat
                    if len(self.subscribers) <= self.max_per_group:
                        print("Plus qu'un seul groupe possible, fin du débat")
                        break

            except Exception as e:
                print(f"ERREUR dans run_steps: {str(e)}")
            finally:
                print(f"Débat '{self.name}' terminé")
                client.send_message({
                    "type": "private",
                    "to": self.creator_email,
                    "content": f"Débat '{self.name}' terminé après {self.step} étapes.",
                })
        threading.Thread(target=run_steps, daemon=True).start()

# Fonctions utilitaires
    
def add_users_to_stream(stream_name: str, user_emails: list[str]) -> bool:
    print(f"Ajout de {user_emails} dans {stream_name}")
    user_ids = [get_user_id(email) for email in user_emails if get_user_id(email)]
    # Ajout de l'ID du bot lui-même
    bot_user_id = get_user_id(get_client().get_profile()["email"])
    if bot_user_id and bot_user_id not in user_ids:
        user_ids.append(bot_user_id)

    if not user_ids:
        return False
    try:
        result = client.add_subscriptions(
            streams=[{"name": stream_name}],
            principals=user_ids,
        )
        print(f"Ajout réussi")
        return result["result"] == "success"
    except Exception as e:
        print(f"Erreur lors de l'ajout des utilisateurs : {e}")
        return False

def notify_users(stream_name: str, user_emails: list[str]) -> None:
    #Notifie les utilisateurs de leur affectation à un groupe.
    print(f"Notification de {user_emails} dans {stream_name}")
    for email in user_emails:
        message = {
            "type": "private",
            "to": email,
            "content": f"Vous avez été affecté au groupe '{stream_name}'.",#Plus de clarté quelle groupe en particilier
        }
        get_client().send_message(message)

def get_user_id(user_email: str) -> str:
    #Récupère l'ID utilisateur à partir de l'email.
    result = client.get_members()
    for user in result["members"]:
        if user["email"] == user_email:
            return user["user_id"]
    return None


def get_email_by_full_name(full_name: str) -> str:
    #Récupère l'email à partir du nom complet.
    try:
        result = client.get_members()
    except AttributeError:
        print(f"Erreur lors de la récupération des membres. La variable ""client"" est elle initialisé ? : {client}")
        return None
    for user in result['members']:
        if user['full_name'].strip().lower() == full_name.strip().lower():
            return user['email']
    return None  # Not found


def get_all_zulip_user_emails():
    result = get_client().get_members()
    return [user["email"] for user in result["members"]]




# Gestion des débats
listeDebat = {}

def handle_message(msg: dict[str, str]) -> None:
    print("Message reçu")
    #print(msg)
    global id_message_stats, stream_stats
    if stream_stats is None:
        stream_stats = msg["display_recipient"]

    # Ignorer les messages envoyés par le bot lui-même
    if msg["sender_email"] == get_client().get_profile()["email"]:
        return
    content = msg["content"].strip()
    user_email = msg["sender_email"]
    nb_caracteres = len(content)
    user_name = msg["sender_full_name"]
    # 1. Statistiques cumulatives
    if user_email not in stats_utilisateurs:
        if user_email != get_client().get_profile()["email"]:
            stats_utilisateurs[user_email] = {"messages": 0, "caracteres": 0, "name": msg["sender_full_name"]}

    stats_utilisateurs[user_email]["messages"] += 1
    stats_utilisateurs[user_email]["caracteres"] += nb_caracteres


    if content.startswith("@créer"):
        print("Commande : créer")
        params = content.split()
        if len(params) < 6:
            client.send_message({
                "type": "private",
                "to": user_email,
                "content": "Usage : @créer <nom> <max_par_groupe> <minutes_avant_fin> <minutes_entre_étapes> <num_pass>",
            })
            return
        name = params[1]
        max_per_group = int(params[2])
        end_date = datetime.now() + timedelta(minutes=int(params[3]))
        time_between_steps = timedelta(minutes=int(params[4]))
        num_pass = int(params[5])
        listeDebat[name] = Debat(name, user_email, max_per_group, end_date, time_between_steps, num_pass)
        client.send_message({"type": "private", "to": user_email,
                             "content": f"Débat '{name}' créé avec succès."})

    elif content.startswith("@configurer"):
        print("Commande : configurer")
        try:
            config_json = json.loads(content.replace("@configurer", "").strip())
            name = config_json["nom"]
            obj = Debat(
                name,
                user_email,
                config_json["max_par_groupe"],
                datetime.now() + timedelta(minutes=config_json["minutes_avant_fin"]),
                timedelta(minutes=config_json["minutes_entre_étapes"]),
                config_json["num_pass"]
            )
            listeDebat[name] = obj
            client.send_message({"type": "private", "to": user_email,
                                 "content": f"Débat '{name}' configuré avec succès."})
        except Exception as e:
            client.send_message({"type": "private", "to": user_email, "content": f"Erreur dans la configuration : {str(e)}"})

    elif content.startswith("@s'inscrire"):
        print("Commande : s'inscrire")
        params = content.split()
        if len(params) < 2:
            return
        name = params[1]
        if name not in listeDebat:
            return
        listeDebat[name].add_subscriber(user_email, {"name": "Utilisateur"})
        client.send_message({"type": "private", "to": user_email,
                             "content": f"Inscription au débat '{name}' confirmée."})

    elif content.startswith("@état"):
        print("Commande : état")
        params = content.split()
        if len(params) < 2:
            return
        name = params[1]
        if name in listeDebat:
            status = listeDebat[name].get_status()
            client.send_message({"type": "private", "to": user_email, "content": status})
    

    # 2. Suivi des messages consécutifs
    if messages_consecutifs["last_sender"] == user_email:
        messages_consecutifs["count"] += 1
    else:
        messages_consecutifs["last_sender"] = user_email
        messages_consecutifs["count"] = 1
    
    mediane = get_mediane_combinee()

    # Avertissement parle trop 
    if stats_utilisateurs[user_email]["messages"] > 4 * mediane:
        get_client().send_message({
            "type": "stream",
            "to": msg["display_recipient"],
            "topic": msg["subject"],
            "content": f"@**{user_name}** ⚠️ Vous avez largement dépassé la participation moyenne. Merci de laisser de la place aux autres."
        })

    # Participation faible 
    active_users = {email: stats for email, stats in stats_utilisateurs.items() if stats["messages"] > 0}
    if len(active_users) >= 3 and mediane >= 2:
        ratio = stats_utilisateurs[user_email]["messages"] / mediane
        maintenant = datetime.now()
        dernier = dernier_alerte_utilisateur.get(user_email, datetime.min)

        if ratio < 0.5 and (maintenant - dernier).total_seconds() > COOLDOWN_ALERTES:
            if ratio < 0.25:
                texte = "⚠️ **Votre participation est très faible** comparée aux autres. Votre avis est important !"
            else:
                texte = "💡 **Vous pourriez participer davantage** - le débat a besoin de votre voix !"

            get_client().send_message({
                "type": "stream",
                "to": msg["display_recipient"],
                "topic": msg["subject"],
                "content": f"@**{user_name}** {texte}"
            })
            dernier_alerte_utilisateur[user_email] = maintenant

    # Générer contenu stat + avertissements globaux

    if stats_utilisateurs:
    # Construire le contenu du message par utilisateur
        lignes = []
        for email, stats in stats_utilisateurs.items():
            nom = stats["name"]
            nb_msg = stats["messages"]
            nb_car = stats["caracteres"]
            lignes.append(f"- **{nom}** : {nb_msg} message(s), {nb_car} caractère(s) envoyés")

        contenu = (
            "**📊 Contribution détaillée des participants**\n\n"
            + "\n".join(lignes)
        )

        if id_message_stats is None:
            result = get_client().send_message({
                "type": "stream",
                "to": stream_stats,
                "topic": "📊 Contribution",
                "content": contenu,
            })
            id_message_stats = result["id"]
        else:
            try:
                get_client().update_message({
                    "message_id": id_message_stats,
                    "content": contenu
                })
            except Exception as e:
                print(f"Erreur mise à jour stats : {e}")


    #Nouveau bloc pour gérer la publication des sondages par les membres choisis
    for debate in listeDebat.values():
        # Vérifie si ce débat a une liste poll_authors et si l'utilisateur en fait partie
        if hasattr(debate, "poll_authors") and user_email in debate.poll_authors:
            stream_name = debate.group_to_stream.get(user_email)

            if content.startswith("/poll"):
                try:
                    # Envoie le message du sondage dans le stream associé au groupe
                    client.send_message({
                        "type": "stream",
                        "to": stream_name,
                        "subject": "Sondage final",
                        "content": content,
                    })
                    # Confirme à l'utilisateur que son sondage est publié
                    client.send_message({
                        "type": "private",
                        "to": user_email,
                        "content": "Ton sondage a bien été publié dans le groupe.",
                    })
                    # Supprime l'utilisateur des listes pour éviter plusieurs sondages
                    del debate.poll_authors[user_email]
                    del debate.group_to_stream[user_email]
                except Exception as e:
                    client.send_message({
                        "type": "private",
                        "to": user_email,
                        "content": f"Erreur lors de l’envoi du sondage : {e}",
                    })
            else:
                # Si le message ne commence pas par /poll, on prévient l'utilisateur
                client.send_message({
                    "type": "private",
                    "to": user_email,
                    "content": "Ton message ne commence pas par `/poll`. Utilise le format `/poll \"Question\" \"Option 1\" \"Option 2\"`.",
                })
            break



#calcul de la médiane
def get_mediane_combinee() -> float:
    if not stats_utilisateurs:
        return 0
    liste_scores = []
    for data in stats_utilisateurs.values():
        score = data["messages"] + data["caracteres"] / 10 
        liste_scores.append(score)
    try:
        return statistics.median(liste_scores)
    except statistics.StatisticsError:
        return 0

def check_and_create_channels() -> None:
    #Vérifie si la période d'inscription est terminée et crée les channels si nécessaire.
    for name, obj in listeDebat.items():
        if datetime.now(timezone.utc) > obj.end_date and not obj.channels_created:
            # Créer les channels et répartir les utilisateurs
            groups = obj.split_into_groups()
            if groups == []:
                print(f"Création de débat imposible pour l'objet D '{name}'. Il n'a pas de participants ou le nombre maximal de participants par groupe est 0.")
                break
            obj.create_streams_for_groups(groups)
            obj.channels_created = True  # Marquer que les channels ont été créés
            print(f"Channels créés pour l'objet D '{name}'.")
            obj.start_debate_process()  # Démarrer le processus de débat

def message_listener() -> None:
    #Fonction pour écouter les messages entrants.
    print("Démarrage de l'écoute des messages...")
    request = {
        "event_types": ["message"],
        "narrow": [],  # vide = écoute tous les messages
        "all_public_streams": True  # écoute même les messages dans les streams publics où il est abonné
    }
    get_client().call_on_each_message(handle_message)

def create_debat() -> None:
    print("Vérification des débats à créer...")
    for debat in Debat.objects.all():
        if not debat.debat_created and debat.is_archived == False:
            # Créer le débat ici
            print(f"Création du débat : {debat.title}")
            # Exemple de création d'un débat
            listeDebat[debat.title] = ObjectD(debat.title, debat.creator_email, debat.max_per_group, debat.end_date, debat.time_between_round, debat.num_pass)
            # Mettre à jour le statut du débat dans la base de données
            debat.debat_created = True
            debat.save()
            print(listeDebat)
            print(f"Débat créé : {debat.title}")

def add_user() -> None:
    print("Vérification des utilisateurs à ajouter...")
    for debat in Debat.objects.all():
        print(f"Vérification des utilisateurs pour le débat : {debat.title}")
        if debat.debat_created:
            for user in debat.debat_participant.all():
                if not user.is_register:
                    # Ajouter l'utilisateur ici
                    print(f"Ajout de l'utilisateur : {user.pseudo}")
                    user.email = get_email_by_full_name(user.pseudo)
                    if(user.email != None):
                        print(listeDebat)
                        listeDebat[debat.title].add_subscriber(user.email, {"name": user.pseudo})
                        user.is_register = True
                        user.save()
                    else: 
                        print(f"Utilisateur {user.pseudo} non trouvé dans Zulip.")

def event_listener():
    print("Démarrage de l'écoute des événements...")
    client.call_on_each_event(handle_reaction, event_types=['reaction'])

def main_loop() -> None:
    #Boucle principale du bot.
    print("Démarrage de la boucle principale...")
    i=0
    
    while True:

        #On génére les debats qui n'ont pas encore été génére depuis la table debat
        create_debat()
        #On ajoute les utilisateurs qui ne sont pas encore inscrits
        #print(listeDebat)
        add_user()
        # Vérifie si la période d'inscription est terminée et crée les channels si nécessaire
        check_and_create_channels()
        #print(get_all_zulip_user_emails())
        
        #print(f"Affichage d'object.\n Object_D : {objects_D}\n Nombre d'object : {len(objects_D)}\n")
        #print(f"Affichager de la base de donnée : {Debat.objects.all()}")
        
        
        #members = client.get_members()
        #print(members)
        """
        owner_id = 26  # from get_profile()
        owner_email = None

        for member in members['members']:
            if member['user_id'] == owner_id:
                owner_email = member['email']
                break

        print("Bot owner email:", owner_email)
        """
        # Attend quelques secondes avant de recommencer
        time.sleep(10)  # Attendre 10 secondes
        
        
        i+=1

if __name__ == "__main__":
    threading.Thread(target=message_listener, daemon=True).start()
    threading.Thread(target=event_listener, daemon=True).start()
    main_loop()
