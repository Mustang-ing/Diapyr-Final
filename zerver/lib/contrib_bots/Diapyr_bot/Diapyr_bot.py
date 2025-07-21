import json
import os
import sys


# Set the settings module from your Zulip settings (adjust path if needed)
sys.path.append("/home/jass/Diapyr/Diapyr-Final") 
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")

import django
django.setup()
import math

import zulip
import random
from datetime import datetime, timedelta, timezone
import time
import threading
from zerver.models.debat import Debat,Participant
import statistics


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
        print(f"Création d'un objet débat : {name}")

    def add_subscriber(self, user_email: str , user_info: dict[str, str]) -> None:
        #Ajoute un utilisateur à la liste des inscrits.
        self.subscribers[user_email] = user_info
        print(f"Ajout du participant {user_email}")


    def split_into_groups(self) -> list[list[str]]:
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

    def next_step(self):
        users = list(self.subscribers.keys())
        if users is None or len(users) == 0:
            print(f"Aucun utilisateur inscrit dans le débat '{self.name}'.")
            return False
        
        num_groups = len(users) //  self.max_per_group 
        for i in range(num_groups):  #On récupere le nombre de groupe de l'étape acutel afin d'avoir leurs stream 
            stream_name = f"{self.name}{'I'*self.step}{i+1}" #On prend leurs noms 
            try:
                stream_id = client.get_stream_id(stream_name)["stream_id"]
                client.delete_stream(stream_id)
                print(f" Archivage du stream {stream_name} ")
            except Exception as e:
                print(f" Erreur sur le stream{stream_name} |  {str(e)}")

                
        
        #On vérifie si leurs nombre est assez grand pour etre divisé OU que le nombre de passes choisit est inférieur OU au moins 2 utilisateurs
        if len(users) <= self.max_per_group or self.step >= self.num_pass or len(users) < 2:
            return False
        
        eliminated = random.sample(users,self.max_per_group)
        users_to_keep = [u for u in users if u not in eliminated]

        if len(users_to_keep) <= self.max_per_group: #Si apres la suppresion enleve trop de personne
            return False
        
        self.subscribers = {u: self.subscribers[u] for u in users_to_keep}
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
    

    def start_debate_process(self) -> None: #N'aurait t'on pas pu faire une seule fonction pour gérer les étapes ? Ou voir les décorateurs ?
        def run_steps() -> None:
            while True:
                print(f"Attente de {self.time_between_steps} avant la prochaine étape...")
                time.sleep(self.time_between_steps.total_seconds())
                if not self.next_step():
                    print(f"Débat '{self.name}' terminé. Plus qu’un seul groupe.")
                    users = list(self.subscribers.keys())
                    print(f"Liste des users: {users}")  
                    for mail in users:
                        print(f"Envoi à: {mail}")  
                        client.send_message({
                            "type": "private",
                            "to": mail,
                            "content": f"Le débat'{self.name}' est terminé. Merci d'avoir participé !",
                        })
                    try:
                        debat = Debat.objects.get(title=self.name)
                        debat.is_archived = True
                        debat.save()
                        print(f"Débat '{self.name}' archivé dans la base de données.")
                    except Debat.DoesNotExist:
                        print(f"Erreur: Débat '{self.name}' non trouvé dans la base de données.")
                    except Exception as e:
                        print(f"Erreur lors de la suppression du débat: {str(e)}")
                    print(f"Suppression du débat{self.name}")                    
                    # Suppression de la liste en mémoire
                    if self.name in listeDebat:
                        del listeDebat[self.name]
                    break
            

                print(f"Étape {self.step} du débat '{self.name}'")
                groups = self.split_into_groups()
                self.create_streams_for_groups(groups)

                client.send_message({
                    "type": "private",
                    "to": self.creator_email,
                    "content": f"Étape {self.step} démarrée pour le débat '{self.name}'.",
                })
        threading.Thread(target=run_steps).start()
    
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

    # Ignorer les messages envoyés par le bot lui-même
    if msg["sender_email"] == get_client().get_profile()["email"]:
        return
    content = msg["content"].strip()
    user_email = msg["sender_email"]
    user_name = msg["sender_full_name"]
    nb_car = len(content)

    if user_email not in stats_utilisateurs:
        stats_utilisateurs[user_email] = {
            "messages": 0,
            "caracteres": 0,
            "name": user_name,
            "is_subscriber": True
        }
        historique_messages[user_email] = []
    
    stats_utilisateurs[user_email]["messages"] += 1
    stats_utilisateurs[user_email]["caracteres"] += nb_car

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
    
    # alerte spam ------------------------------------------------------------------------
    now = datetime.now()
    if user_email not in historique_messages:
        historique_messages[user_email] = []

    # Ajout du temps d'envoi du message actuel à l'historique 
    historique_messages[user_email].append(now)

    # Garder uniquement les messages des 10 dernières secondes
    historique_messages[user_email] = [
        t for t in historique_messages[user_email]
        if (now - t).total_seconds() <= 10
    ]

    # Vérifier si l'utilisateur spamme
    if len(historique_messages[user_email]) > 5:
        get_client().send_message({
            "type": "stream",
            "to": msg["display_recipient"],
            "topic": msg["subject"],
            "content": f"@**{msg['sender_full_name']}** ⚠️ Vous envoyez trop de messages en peu de temps. Merci de ralentir pour laisser les autres s’exprimer."
        })
        historique_messages[user_email] = []  # Réinitialise pour ne pas répéter l’alerte
    
    # Affichage des autres alertes ---------------------------------------------------
    if len(stats_utilisateurs) >= 2:
        med_msg = get_mediane()
        #si la mediane des messages est inférieure à 2, trop tôt pour alerter
        if med_msg >= 2:
            user_msgs = stats_utilisateurs.get(user_email, {}).get("messages", 0)
            if user_msgs > 2 * med_msg and user_msgs >= 5: # Au moins 5 msgs
                get_client().send_message({
                    "type": "stream",
                    "to": msg["display_recipient"],
                    "topic": msg["subject"],
                    "content": f"@**{msg['sender_full_name']}** ⚠️ Vous avez envoyé trop de messages (médiane: {med_msg}). Merci de laisser de la place aux autres."
                })
             # Participation faible (messages)
            ratio_msg = user_msgs / med_msg if med_msg > 0 else 0
            maintenant = datetime.now()
            dernier = dernier_alerte_utilisateur.get(user_email, datetime.min)
            COOLDOWN = max(300, len(stats_utilisateurs) * 30)
            if 0 < ratio_msg < 0.5 and (maintenant - dernier).total_seconds() > COOLDOWN :
                if ratio_msg < 0.25 : 
                    texte = "⚠️ **Votre participation est très faible** comparée aux autres. Votre avis est important !"
                elif ratio_msg < 0.5:
                    texte = "💡 **Vous pourriez participer davantage** - le débat a besoin de votre voix !"
                else:
                    return
                def envoyer_alerte():
                    get_client().send_message({
                        "type": "stream",
                        "to": msg["display_recipient"],
                        "topic": msg["subject"],
                        "content": f"@**{user_name}** {texte} (vous: {user_msgs} msg, moyenne du chat: {med_msg})"
                    })
                timer = threading.Timer(30.0, envoyer_alerte)
                timer.start()
                dernier_alerte_utilisateur[user_email] = maintenant    

    # Affichage des statistiques de participation --------------------------------------------------
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
                "to": msg["display_recipient"],
                "topic": "📊 Contribution",
                "content": contenu,
            })
            if result["result"] == "success":
                id_message_stats = result["id"]
            else:
                print(f"Erreur lors de l'envoi du message de stats : {result.get('msg', 'Erreur inconnue')}")
        else:
            try:
                get_client().update_message({
                    "message_id": id_message_stats,
                    "content": contenu
                })
            except Exception as e:
                print(f"Erreur mise à jour stats : {e}")

#calcul de la médiane, retourne un tuple (médiane des messages, médiane des caracteres)
def get_mediane() -> float:
    """Retourne uniquement la médiane des messages"""
    if not stats_utilisateurs or len(stats_utilisateurs) < 3:
        return 0.0
    
    try:
        messages = [u["messages"] for u in stats_utilisateurs.values() if u["messages"] > 0]
        return float(statistics.median(messages)) if messages else 0.0
    except Exception as e:
        print(f"Erreur calcul médiane: {str(e)}")
        return 0.0

        
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
    current_time = datetime.now(timezone.utc)
    for debat in Debat.objects.all():
        print(f"Vérification pour le débat : {debat.title}")
        if debat.debat_created and debat.title in listeDebat and not debat.is_archived:
            obj = listeDebat[debat.title]
            # Vérifie si la période d'inscription est terminée
            if current_time > obj.end_date:
                #-------------------------Partie message au créateur-------------------------------------------
                email =""#Vide à cause du probleme de compte
                participant = len(obj.subscribers)

                message = {
                    "type": "private",
                    "to": email,
                    "content": f"Vous avez crée le débat '{debat.title}' \n Il compose à présent '{participant}' personnes à son actif\n Veillez entrer le nombre d'élue à faire passer : ",
                }
                #-----------------------------------------------------------------------------------------------
                
                for user in debat.debat_participant.all():
                    if not user.is_register:
                        print(f"Ajout de l'utilisateur : {user.pseudo}")
                        user.email = get_email_by_full_name(user.pseudo)
                        if user.email is not None:
                            obj.add_subscriber(user.email, {"name": user.pseudo})
                            user.is_register = True
                            user.save()
                        else:
                            print(f"Utilisateur {user.pseudo} non trouvé dans Zulip.")
            else:
                print(f"Période d'inscription toujours en cours pour '{debat.title}'. Fin prévue à {obj.end_date}.")

def main_loop() -> None:
    #Boucle principale du bot.
    print("Démarrage de la boucle principale...")
    i=0 #Utilité ?
    #get_client()  
    while True:

        #print(client.get_members())
         #print(members)
        #On génére les debats qui n'ont pas encore été génére depuis la table debat
        create_debat()
        #On ajoute les utilisateurs qui ne sont pas encore inscrits
        #print(listeDebat)
        add_user()
        # Vérifie si la période d'sinscription est terminée et crée les channels si nécessaire
        check_and_create_channels()

       

        #print(get_all_zulip_user_emails())
        
        #print(f"Affichage d'object.\n Object_D : {objects_D}\n Nombre d'object : {len(objects_D)}\n")
        #print(f"Affichager de la base de donnée : {Debat.objects.all()}")

        # Attend quelques secondes avant de recommencer
        time.sleep(10)  # Attendre 10 secondes
        
        
        i+=1

if __name__ == "__main__":
    threading.Thread(target=message_listener).start()
    main_loop()
