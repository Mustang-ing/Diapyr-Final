import os
import django

# Set the settings module from your Zulip settings (adjust path if needed)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
django.setup()
import zulip
import random
from datetime import datetime, timedelta, timezone
import time
import threading
from zerver.models.debat import Debat,Participant

# Configuration du bot
client = None

def get_client():
    #Initialise le client Zulip.
    global client
    if client is None:
        client = zulip.Client(config_file="zuliprc.txt")
        print("Client Zulip initialisé avec succès !")
    return client

class ObjectD:
    def __init__(self, name, creator_email, max_per_group, end_date, time_between_steps, num_pass):
        self.name = name
        self.creator_email = creator_email
        self.max_per_group = max_per_group
        self.end_date = end_date
        self.time_between_steps = time_between_steps
        self.num_pass = num_pass
        self.step = 1
        self.subscribers = {}
        self.channels_created = False
        print(f"Création d'un objet débat : {name}")

    def add_subscriber(self, user_email, user_info):
        #Ajoute un utilisateur à la liste des inscrits.
        self.subscribers[user_email] = user_info
        print(f"Ajout du participant {user_email}")

    #La fonction split_into_groups répartit les utilisateurs en groupes de taille max_per_group,depuis la liste des inscrit (via leur clé).
    #Elle mélange d'abord la liste des utilisateurs, puis les divise en groupes de taille max_per_group.
    def split_into_groups(self):
        #Répartit les utilisateurs en groupes.
        print("split_into_groups")
        users = list(self.subscribers.keys())
        random.shuffle(users)
        groups = [users[i:i + self.max_per_group] for i in range(0, len(users), self.max_per_group)]
        return groups
    
    def create_streams_for_groups(self, groups):
        #Crée des streams pour chaque groupe.
        print("Création d'un channel pour les groupes")
        streams = []
        for i, group in enumerate(groups):
            stream_name = self.name + self.step*"I"+f"{i+1}" # = f"{self.name}I#{self.step}#{i + 1}"
            if create_stream(stream_name):
                if add_users_to_stream(stream_name, group):
                    notify_users(stream_name, group)
                    streams.append(stream_name)
        return streams

    def next_step(self):
        #Passe à l'étape suivante.
        print("Passage à l'étape suivante")
        users = list(self.subscribers.keys())
        if len(users) <= self.max_per_group:
            return False  #Fin

        # Sélectionner les utilisateurs pour l'étape suivante
        selected_users = random.sample(users, min(self.num_pass * (len(users) // self.max_per_group, len(users))))

        # Mettre à jour la liste des inscrits
        self.subscribers = {user: self.subscribers[user] for user in selected_users}
        self.step += 1
        return True

# Fonctions utilitaires
def create_stream(stream_name):
    #Crée un stream dans Zulip.
    print(f"Création d'un channel : {stream_name}")
    # Utiliser add_subscriptions pour créer un stream
    result = get_client().add_subscriptions(
        streams=[{
            "name": stream_name,
            "description": f"Groupe pour l'objet D '{stream_name}'",
            "invite_only": True,  # Stream privé
            "history_public_to_subscribers": True,  # Historique partagé
        }]
    )
    if result["result"] == "success":
        print(f"Stream '{stream_name}' créé avec succès.")
        return True
    else:
        print(f"Erreur lors de la création du stream '{stream_name}': {result.get('msg', 'Pas de message d\'erreur')}")
        return False
    
def add_users_to_stream(stream_name, user_emails):
    #Ajoute des utilisateurs à un stream.
    print(f"Ajout de {user_emails} dans {stream_name}")
    user_ids = [get_user_id(email) for email in user_emails]
    print(f"Affichage de tous les email #{get_all_zulip_user_emails()}")
    if None in user_ids:
        print(f"Erreur : Impossible de récupérer l'ID d'un ou plusieurs utilisateurs.")
        return False

    # Ajouter les utilisateurs au stream
    result = client.add_subscriptions(
        streams=[{"name": stream_name}],
        principals=user_ids,
    )
    if result["result"] == "success":
        print(f"Utilisateurs ajoutés au stream '{stream_name}'.")
        return True
    else:
        print(f"Erreur lors de l'ajout des utilisateurs au stream '{stream_name}': {result.get('msg', 'Pas de message d\'erreur')}")
        return False

def notify_users(stream_name, user_emails):
    #Notifie les utilisateurs de leur affectation à un groupe.
    print(f"Notification de {user_emails} dans {stream_name}")
    for email in user_emails:
        message = {
            "type": "private",
            "to": email,
            "content": f"Vous avez été affecté au groupe '{stream_name}'.",
        }
        get_client().send_message(message)


def is_valid_zulip_email(email):
    users = get_client().get_members()["members"]
    return email in [u["email"] for u in users]

def get_user_id(user_email):
    #Récupère l'ID d'un utilisateur à partir de son email.
    request = {
        "client_gravatar": True,
        "include_custom_profile_fields": False,
    }
    result = get_client().get_members(request)
    for user in result["members"]:
        if user["email"] == user_email:
            return user["user_id"]
    return None


def get_all_zulip_user_emails():
    result = get_client().get_members()
    return [user["email"] for user in result["members"]]



# Gestion des objets D
objects_D = {}

def handle_message(msg):
    #Gère les messages reçus par le bot.
    print(f"Message reçu")
    content = msg["content"].strip()
    user_email = msg["sender_email"]

    if content.startswith("@créer"):
        print("On est dans créer là")
        params = content.split()
        if len(params) < 6:
            get_client().send_message({
                "type": "private",
                "to": user_email,
                "content": "Usage : @créer <nom> <max_par_groupe> <jours_avant_fin> <jours_entre_étapes> <num_pass>",
            })
            return

        name = params[1]
        max_per_group = int(params[2])
        end_date = datetime.now() + timedelta(minutes=int(params[3]))
        time_between_steps = timedelta(minutes=int(params[4]))
        num_pass = int(params[5])

        objects_D[name] = ObjectD(name, user_email, max_per_group, end_date, time_between_steps, num_pass)
        get_client().send_message({
            "type": "private",
            "to": user_email,
            "content": f"Objet D '{name}' créé avec succès.",
        })

    elif content.startswith("@s'inscrire"):
        print("Et ici dans s'inscrire")
        params = content.split()
        if len(params) < 2:
            get_client().send_message({
                "type": "private",
                "to": user_email,
                "content": "Usage : @s'inscrire <nom>",
            })
            return

        name = params[1]
        if name not in objects_D:
            get_client().send_message({
                "type": "private",
                "to": user_email,
                "content": f"L'objet D '{name}' n'existe pas.",
            })
            return

        objects_D[name].add_subscriber(user_email, {"name": "John Doe"})  # Remplace par les infos réelles
        get_client().send_message({
            "type": "private",
            "to": user_email,
            "content": f"Vous êtes inscrit à l'objet D '{name}'.",
        })

    elif content.startswith("@continuer"):
        get_client().send_message({
            "type": "private",
            "to": user_email,
            "content": "Redirection vers Zulip...",
        })

def check_and_create_channels():
    #Vérifie si la période d'inscription est terminée et crée les channels si nécessaire.
    for name, obj in objects_D.items():
        if datetime.now(timezone.utc) > obj.end_date and not obj.channels_created:
            # Créer les channels et répartir les utilisateurs
            groups = obj.split_into_groups()
            obj.create_streams_for_groups(groups)
            obj.channels_created = True  # Marquer que les channels ont été créés
            print(f"Channels créés pour l'objet D '{name}'.")

def message_listener():
    #Fonction pour écouter les messages entrants.
    print("Démarrage de l'écoute des messages...")
    get_client().call_on_each_message(handle_message)

def create_debat():
    for debat in Debat.objects.all():
        if not debat.debat_created:
            # Créer le débat ici
            print(f"Création du débat : {debat.title}")
            # Exemple de création d'un débat
            objects_D[debat.title] = ObjectD(debat.title, debat.creator_email, debat.max_per_group, debat.end_date, debat.time_between_round, debat.num_pass)
            # Mettre à jour le statut du débat dans la base de données
            debat.debat_created = True
            debat.save()
            print(f"Débat créé : {debat.title}")

def add_user():
    for debat in Debat.objects.all():
        if debat.debat_created:
            for user in debat.debat_participant.all():
                if not user.is_register:
                    # Ajouter l'utilisateur ici
                    print(f"Ajout de l'utilisateur : {user.email}")
                    objects_D[debat.title].add_subscriber(user.email, {"name": "John Doe"})
                    user.is_register = True
                    user.save()

def main_loop():
    #Boucle principale du bot.
    print("Démarrage de la boucle principale...")
    i=0
    while True:

        #On génére les debats qui n'ont pas encore été génére depuis la table debat
        create_debat()
        #On ajoute les utilisateurs qui ne sont pas encore inscrits
        add_user()
        # Vérifie si la période d'inscription est terminée et crée les channels si nécessaire
        check_and_create_channels()
        
        # Attend quelques secondes avant de recommencer
        time.sleep(10)  # Attendre 10 secondes
        print(i)
        #print(f"Affichage d'object.\n Object_D : {objects_D}\n Nombre d'object : {len(objects_D)}\n")
        #print(f"Affichager de la base de donnée : {Debat.objects.all()}")
        print(get_all_zulip_user_emails())
        #cli = client.get_profile()
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
        i+=1

# Démarrer la boucle principale
if __name__ == "__main__":
    # Lancer la gestion des messages dans un thread séparé
    message_thread = threading.Thread(target=message_listener)
    message_thread.start()

    # Démarrer la boucle principale
    main_loop()
