import json
import os
import django
import sys

from zerver.lib.diapyr import main_db, split_into_group_db, create_streams_for_groups_db_via_api, create_streams_for_groups_db


# Set the settings module from your Zulip settings (adjust path if needed)
sys.path.append("/home/ghostie/Diapyr/Diapyr-Final")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
django.setup()
import math

import zulip
import random
from datetime import datetime, timedelta, timezone
import time
import threading
from zerver.models.debat import Debat,Participant,Group
import statistics
from zerver.models import (
    UserProfile,
)    

from typing import Dict, List, Set
from bs4 import BeautifulSoup

# Configuration du bot
client = None

# Statistiques pour voir le nb de msg/caracteres envoyés:
stats_utilisateurs = {}  # email → {"messages": 0, "caracteres": 0}
messages_consecutifs = {"last_sender": None, "count": 0}
# Pour le suivi des alertes de participation faible
dernier_alerte_utilisateur = {}  # email → datetime de la dernière alerte
COOLDOWN = 300
dernier_rappel = None
#pour laffichage des stat
id_message_stats = None  # contiendra l'ID du message à mettre à jour
stream_stats = None  # contiendra le nom du stream où poster les stats

historique_messages = {}
inscrits_debat = {}  # Pour stocker les inscrits aux débat
participants ={}  # Pour stocker les participants aux débats
debut_debat = datetime.now()  # Date de début du débat

def get_client() -> None:
    #Initialise le client Zulip.
    global client
    if client is None:
        client = zulip.Client(config_file="zerver/lib/contrib_bots/Diapyr_bot/zuliprc.txt")
        print("Client Zulip initialisé avec succès !")
    return client

class ObjectD:
    def __init__(self, name: str , creator: UserProfile , creator_email: str , max_per_group: str , subscription_end_date: datetime, time_between_steps: timedelta) -> None:
        self.name = name
        self.creator = creator
        self.creator_email = creator_email
        self.max_per_group = max_per_group
        self.subscription_end_date = subscription_end_date
        self.time_between_steps = time_between_steps if isinstance(time_between_steps, timedelta) else timedelta(seconds=int(time_between_steps))
        #Il pourrait être intéressant de ettre un contrôle sur la valeur du time between_step 
        self.step = 1
        self.subscribers = {} #{"user_email": {"name": "User Name"}}
        self.channels_created = False
        # Structures pour gérer les sondages
        self.selected: list[str] = []           # [emails]
        self.group_members: Dict[str, List[str]] = {}  # {stream_name: [emails]}

        print(f"Création d'un objet débat : {name}")

    def update(self, **kwargs) -> None:
        #Met à jour les attributs de l'objet avec les valeurs fournies.
        for key, value in kwargs.items():
            setattr(self, key, value)
        print(f"Objet D mis à jour : {self.name} - {kwargs}")

    def add_subscriber(self, user_email: str , user_info: dict[str, str]) -> None:
        #Ajoute un utilisateur à la liste des inscrits.
        self.subscribers[user_email] = user_info
        print(f"Ajout du participant {user_email}")

    def split_into_groups(self) -> list[list[str]]:
        print("Répartition des utilisateurs en groupes...")
        users = list(self.subscribers.keys())
        random.shuffle(users)  
    
        n = len(users) 
        m = self.max_per_group  

        if n <= m:
            return [users]

    
        print(f"Nombre de participants : {n}, Nombre maximal de participants par groupe : {m}")
        try:
            num_groups = math.ceil(n/m)
            print( math.ceil(n/m))
            print(f"Nombre de groupes calculé : {num_groups}")
        except ZeroDivisionError:
            return []


        
        min_per_group = n // num_groups
        r = n % num_groups
        groups = []
        print(f"Resultatat de la division : reste = {r}, min_per_group = {min_per_group}, max_per_group = {self.max_per_group}")
        start = 0
        for i in range(num_groups):
            group_size = min_per_group + (1 if i < r else 0) # On fait +1 tant que le nombre de peronne problématique n'est pas traité 
            print(f"groupe size {group_size}")
            groups.append(users[start:start + group_size])
            start += group_size

        print(f"Groupes créés : {len(groups)} - Groupes : {groups}")


        #Methode avec la base de donné : 

        #split_into_group_db(Debat.objects.get(title=self.name), self.max_per_group)
        return groups
    
    def create_streams_for_groups(self, groups: list[list[str]]) -> list[str]:
        #Crée des streams pour chaque groupe et ajoute les utilisateurs.
        print("Ajout des utilisateurs dans les streams existants...")
        
        streams = []
        for i, group in enumerate(groups):
            stream_name = self.name + f"Tour {self.step} - Groupe {i+1}" #Changer le nom pour plus de clarté
            print(f"Tentative d'ajout dans le stream : {stream_name}")
            if add_users_to_stream(stream_name, group):
                notify_users(stream_name, group)
                streams.append(stream_name)
        
        #result1 = create_streams_for_groups_db(Group.objects.filter(debat_id=Debat.objects.get(title=self.name).debat_id), self.creator)
        #result2 = create_streams_for_groups_db_via_api(Group.objects.filter(debat_id=Debat.objects.get(title=self.name).debat_id), 124)
        
        return streams
    


    def get_status(self) -> str:
        users = list(self.subscribers.keys())
        if self.creator_email not in users:
            users.append(self.creator_email)
        groups = [users[i:i + self.max_per_group] for i in range(0, len(users), self.max_per_group)]
        for group in groups:
            group.append(self.creator_email)
        info = f"Nom: {self.name}\nÉtape: {self.step}\nFin inscription: {self.subscription_end_date}\nTemps entre étapes: {self.time_between_steps}\n"
        info += f"Nombre de groupes: {len(groups)}\n"
        for idx, group in enumerate(groups):
            info += f"Groupe {idx + 1}: {', '.join(group)}\n"
        return info

    
    # Méthode pour envoyer une question d'enquette pour tous les participants

    def send_enquete(self, group_members: list[str]) -> None:
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

    
    def send_poll2(self,stream_name: str, candidates: List[str]) -> Set[str]:
        print(f"Envoi du sondage final pour {stream_name} avec candidats: {candidates}")
        if stream_name not in self.group_members:
            print(f"Unknown stream: {stream_name}")
            return set()
        
        group = self.group_members[stream_name]
        if not group or not candidates:
            print(f"No valid candidates in {stream_name}")
            return set()
        
         # Get member names
        try:
            all_members = get_all_zulip_user_emails()
            email_to_name = {m["email"]: m["full_name"] for m in all_members}
            #print(f"Members fetched for {stream_name}: {email_to_name}")
        except Exception as e:
            print(f"Error getting members: {e}")
            return set()


    def send_poll(self, stream_name: str, candidates: List[str]) -> Set[str]:
        """Send final poll and process votes allowing multiple votes per member."""
        print(f"Envoi du sondage final pour {stream_name} avec candidats: {candidates}")
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
            #print(f"Members fetched for {stream_name}: {email_to_name}")
        except Exception as e:
            print(f"Error getting members: {e}")
            return set()

        # Filter valid candidates
        valid_candidates = [c for c in candidates if c in group and c in email_to_name]
        print(f"Valid candidates for {stream_name}: {valid_candidates}")
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
        time.sleep(30)  # Wait 2 minutes for votes
        
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

    def next_step(self) -> bool:
        print("Passage à l'étape suivante...")
        # 1. Création des groupes
        users = list(self.subscribers.keys())
        if users is None or len(users) == 0:
            print(f"Aucun utilisateur inscrit dans le débat '{self.name}'.")
            return False
       
        # 2. Envoi des MPs
        for stream_name in self.group_members:
            self.send_enquete(self.group_members[stream_name])
            print(f"envoie enquete au stream {stream_name}...")

        # 3. Attente des réponses
        print("\nEn attente des réponses à l'enquéte...")
        time.sleep(45)  # Attendre 20 secondes pour les réponses

        # 4. Traitement des réponses
        #A paraleliser, on fait de manière séquentielle pour chaque streams c'est trop lent
        selected_members = set()
        for stream_name in self.group_members:
            responders = self.collect_reponses(stream_name)
            #print(f"Réponses collectées pour {stream_name}: {responders}")
            if responders:
                selected = self.send_poll(stream_name, responders)
                selected_members.update(selected)

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
                    print(f"Groupes créés : {stream_names}")

                    # 2. Envoi des MPs
                    for stream_name in stream_names:
                        self.send_enquete(self.group_members[stream_name])
                    print(f"envoie enquete...")

                    # 3. Attente des réponses
                    print("\nEn attente des réponses à l'enquéte...")
                    time.sleep(45)  # Attendre 20 secondes pour les réponses

                    # 4. Traitement des réponses
                    selected_members = set()
                    for stream_name in stream_names:
                        responders = self.collect_reponses(stream_name)
                        #print(f"Réponses collectées pour {stream_name}: {responders}")
                        if responders:
                            selected = self.send_poll(stream_name, responders)
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
                    print(f"Membres sélectionnés pour l'étape {self.step}: {selected_members}")
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
    if not user_ids:
        return False
    try:
        result = client.add_subscriptions(
            streams=[{"name": stream_name}],
            principals=user_ids,
        )
        print(f"Résultat ajout utilisateurs: {result}")
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
            "content": f"Vous avez été affecté au groupe '{stream_name}'.",
        }
        get_client().send_message(message)

def get_user_id(user_email: str) -> str:
    #Récupère l'ID utilisateur à partir de l'email.
    result = client.get_members()
    for user in result["members"]:
        if user["email"] == user_email:
            return user["user_id"]
    return None

# Fonction a retirer
def get_email_by_full_name(full_name: str) -> str: 
    #Récupère l'email à partir du nom complet.
    result = client.get_members()
    for user in result['members']:
        if user['full_name'].strip().lower() == full_name.strip().lower():
            return user['email']
    return None  # Not found

#Fonction a retirer
def get_all_zulip_user_emails():
    result = get_client().get_members()
    return [user["email"] for user in result["members"]]




# Gestion des débats
listeDebat = {}

def handle_message(msg: dict[str, str]) -> None:
    print("Message reçu")
    print(msg["content"])
    content = msg["content"].strip()
    user_email = msg["sender_email"]

    if content.startswith("@créer"):
        print("Commande : créer")
        params = content.split()
        if len(params) < 6:
            client.send_message({
                "type": "private",
                "to": user_email,
                "content": "Usage : @créer <nom> <max_par_groupe> <minutes_avant_fin> <minutes_entre_étapes>",
            })
            return
        name = params[1]
        max_per_group = int(params[2])
        subscription_end_date = datetime.now() + timedelta(minutes=int(params[3]))
        time_between_steps = timedelta(minutes=int(params[4]))
        listeDebat[name] = Debat(name, user_email, max_per_group, subscription_end_date, time_between_steps)
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



def check_and_create_channels() -> None:
    #Vérifie si la période d'inscription est terminée et crée les channels si nécessaire.
    for name, obj in listeDebat.items():
        debat_obj = Debat.objects.get(title=name)
        if datetime.now(timezone.utc) > obj.subscription_end_date and not obj.channels_created: # On devrait utiliser le step ou le statut du débat pour savoir si on a déjà créé les channels.
            # Créer les channels et répartir les utilisateurs
            debat_obj.step = 2
            debat_obj.save()
            print(f"Etape du débat : {debat_obj.step}")
            obj.step = 2  # Update the in-memory ObjectD instance as well
            #Içi on rajoute la condition pour vérifier la date de début du débat
            print(f" La débat {name} commencera à {debat_obj.start_date}")
            if debat_obj.start_date is not None and debat_obj.start_date < datetime.now(timezone.utc):
                debat_obj.step=3
                debat_obj.save()
                obj.update(max_per_group=debat_obj.max_per_group, time_between_steps=debat_obj.time_between_round)
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
    get_client().call_on_each_message(handle_message)

#A suppr dans le futur, car on devrait se suffir de la BDD.
def create_debat() -> None:
    print("Vérification des débats à créer...")
    for debat in Debat.objects.all():
        if not debat.debat_created:
            # Créer le débat ici
            print(f"Création du débat : {debat.title}")
            # Exemple de création d'un débat
            listeDebat[debat.title] = ObjectD(debat.title, debat.creator, debat.creator.email, debat.max_per_group, debat.subscription_end_date, debat.time_between_round)
            # Mettre à jour le statut du débat dans la base de données
            debat.debat_created = True
            debat.save()
            print(listeDebat)
            print(f"Débat créé : {debat.title}")


#A suppr dans le futur, car on devrait se suffir de la BDD
def add_user() -> None:
    print("Vérification des utilisateurs à ajouter...")
    for debat in Debat.objects.all():
        if debat.debat_created and debat.title in listeDebat and not debat.is_archived:
            print("Vérification des utilisateurs à ajouter au débat : ", debat.title )
            obj = listeDebat[debat.title]
            # Vérifie si la période d'inscription est terminée
            #Dans la V 0.9, on ne vérifie pas la prériode d'inscription (Géré coté frontend), on devra checker la date de début du débat
            if current_time > obj.subscription_end_date: # Pq vérifier après avoir charger obj ? Possibilité de fusionner cette condition avec la précédente ?
                #-------------------------Partie message au créateur-------------------------------------------
                email =""#Vide à cause du probleme de compte
                participant = len(obj.subscribers)

                message = {
                    "type": "private",
                    "to": email,
                    "content": f"Vous avez crée le débat '{debat.title}' \n Il compose à présent '{participant}' personnes à son actif\n Veillez entrer le nombre d'élue à faire passer : ",
                }
                #-----------------------------------------------------------------------------------------------
                
                for user in debat.debat_participants.all():
                    participant = Participant.objects.get(user=user, debat=debat)
                    if not participant.is_registered_to_a_debate:
                        print(f"Ajout de l'utilisateur : {user.full_name} avec l'email {user.email}")
                        if user.email is not None:
                            obj.add_subscriber(user.email, {"name": user.full_name})
                            participant.is_registered_to_a_debate = True
                            participant.save()
                        else:
                            print(f"Utilisateur {user.full_name} non trouvé dans Zulip.")
            else:
                print(f"Période d'inscription toujours en cours pour '{debat.title}'. Fin prévue à {obj.subscription_end_date}.")


def event_listener():
    print("Démarrage de l'écoute des événements...")
    client.call_on_each_event(handle_reaction, event_types=['reaction'])

def main_loop() -> None:
    #Boucle principale du bot.
    print("Démarrage de la boucle principale...")
    i=0 #Utilité ?
    #get_client()  
    threading.Thread(target=message_listener).start()
    threading.Thread(target=event_listener, daemon=True).start()

   
    while True:
        #print(client.get_members())
        #print(members)
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

        # Attend quelques secondes avant de recommencer
        time.sleep(10)  # Attendre 10 secondes
        i+=1

