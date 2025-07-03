import json
import os
import django
import sys
# Set the settings module from your Zulip settings (adjust path if needed)
sys.path.append("/home/ghostie/Diapyr/Diapyr-Final")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
django.setup()
import zulip
import random
from datetime import datetime, timedelta, timezone
import time
import threading
from zerver.models.debat import Debat,Participant
import random
import math
# Configuration du bot
client = None

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
        self.num_pass = num_pass
        self.step = 1
        self.subscribers = {}
        self.channels_created = False
        # Structures pour gérer les QCM et sondages
        self.qcm_data: Dict[str, Dict[str, Set[str]]] = {}
        self.qcm_message_ids: Dict[str, int] = {}  # {stream_name: message_id}
        self.qcm_events: Dict[str, threading.Event] = {}  # {stream_name: Event}
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
            stream_name = self.name + self.step * "I" + f"{i+1}"
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

    
    # Méthode  pour envoyer le sondage final basé sur les réponses QCM
    def send_qcm(self, stream_name: str, group_members: list[str]) -> bool:
        """Retourne True si le QCM est envoyé avec succès"""
        try:
            # Vérifier/créer le stream
            stream_info = client.get_stream_id(stream_name)
            if stream_info.get("result") != "success":
                print(f"Création du stream {stream_name}...")
                client.add_subscriptions(
                    streams=[{"name": stream_name}],
                    principals=[get_user_id(email) for email in group_members],
                )

            # Préparer le message
            all_members = client.get_members()["members"]
            email_to_name = {m["email"]: m["full_name"] for m in all_members}
            names = [email_to_name.get(email, email) for email in group_members]
            
            message = {
                "type": "stream",
                "to": stream_name,
                "subject": "QCM",
                "content": "Qui voulez-vous sélectionner ?(repondez :1: pour i ème membre dans le QCM\n\n" + 
                        "\n".join(f"{i}. {name}" for i, name in enumerate(names, 1)),
            }

            # Envoyer et vérifier
            response = client.send_message(message)
            if "id" not in response:
                print(f"Erreur: pas d'ID dans la réponse: {response}")
                return False

            self.qcm_message_ids[stream_name] = response["id"]
            self.qcm_data[stream_name] = {str(i): set() for i in range(1, len(names)+1)}
            self.qcm_events[stream_name] = threading.Event()
            return True

        except Exception as e:
            print(f"Erreur send_qcm: {str(e)}")
            return False
        # fonction pour envoyer sondage final

    def send_final_poll(self, stream_name: str) -> set[str]:
        if stream_name not in self.qcm_data:
            print(f"Aucune donnée QCM pour {stream_name}")
            return set()

        group = self.group_members[stream_name]
        group_size = len(group)

        if group_size <= 1:
            print(f"Pas assez de membres dans {stream_name} pour voter")
            return set()

        # Seuil initial = 2/3 des autres membres
        threshold_high = math.ceil((group_size - 1) * (2 / 3))
        # Seuil secondaire = 1/2 des autres membres (arrondi vers le bas)
        threshold_low = math.floor((group_size - 1) * (1 / 2))

        # Compter les votes reçus
        vote_count = {}
        for option_num, voters in self.qcm_data[stream_name].items():
            if voters:
                index = int(option_num) - 1
                if 0 <= index < group_size:
                    member_email = group[index]
                    vote_count[member_email] = vote_count.get(member_email, 0) + len(voters)

        print(f"Résultats QCM ({stream_name}) : {vote_count}")
        print(f"Seuil de sélection = {threshold} votes")

        # Garder ceux qui atteignent ou dépassent le seuil
        selected = {email for email, count in vote_count.items() if count >= threshold }
        # Si vide, utiliser le seuil bas
        if not selected:
            selected = {email for email, count in vote_count.items() if count >= threshold_low}
        # Envoi du sondage final 
        all_members = client.get_members()["members"]
        email_to_name = {user["email"]: user["full_name"] for user in all_members}
        options = [f'"{email_to_name[email]}"' for email in selected if email in email_to_name]

        if options:
            question = "Vote final : Votez pour vos élus ?"
            poll_command = f'/poll "{question}" {" ".join(options)}'
            message = {
                "type": "stream",
                "to": stream_name,
                "subject": "Sondage final",
                "content": poll_command,
            }
            client.send_message(message)
            print(f"Sondage final envoyé dans {stream_name}")
        else:
            print(f"Aucun membre n’a atteint le seuil dans {stream_name}")

        return selected


    # fonction pour traiter les réponses dans le  QCM
    def handle_reaction(self, event: dict) -> None:
        if event["type"] != "reaction":
            return
            
        message_id = event["message_id"]
        user_email = event["user"]["email"]
        emoji = event["emoji_name"]
        
        # Trouver à quel QCM cette réaction appartient
        stream_name = next(
            (s for s, mid in self.qcm_message_ids.items() if mid == message_id),
            None
        )
        
        if not stream_name:
            return  # Ce n'est pas une réaction à un de nos QCM
            
        # Vérifier que l'utilisateur fait partie du groupe
        if user_email not in self.group_members.get(stream_name, []):
            return
            
        # Vérifier que la réaction est un numéro valide (1, 2, 3...)
        emoji = event["emoji_name"].strip(':')  # Transforme ":1:" → "1"
        if emoji.isdigit():
            self.qcm_data[stream_name][emoji].add(user_email)
            # Enregistrer la réponse
            self.qcm_data[stream_name][emoji].add(user_email)
            print(f"Vote {emoji} enregistré de {user_email} dans {stream_name}")
            
            # Vérifier si tous ont répondu
            expected = set(self.group_members[stream_name])
            responded = set().union(*self.qcm_data[stream_name].values())  # Tous les votants
            
            if expected.issubset(responded):
                print(f"Toutes les réponses reçues pour {stream_name}")
                self.qcm_events[stream_name].set()

   

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

                    # 2. Envoi des QCM
                    qcm_success = True
                    for stream_name, group in zip(stream_names, groups):
                        if not self.send_qcm(stream_name, group):
                            qcm_success = False
                            print(f"Échec QCM pour {stream_name}")

                    if not qcm_success:
                        print("Échec d'envoi des QCM, passage à l'étape suivante")
                        self.step += 1
                        continue

                    # 3. Attente des réponses
                    print("\nEn attente des réponses aux QCM...")
                    start_time = time.time()
                    timeout = 180  # 3 minutes
                    all_responded = False

                    while (time.time() - start_time) < timeout:
                        all_responded = all(event.is_set() for event in self.qcm_events.values())
                        if all_responded:
                            break
                        time.sleep(5)  # Vérifier toutes les 5s

                    # 4. Traitement des réponses
                    selected_members = set()
                    for stream_name in stream_names:
                        if self.qcm_events[stream_name].is_set():
                            selected = self.send_final_poll(stream_name)
                            selected_members.update(selected)
                        else:
                            print(f"Timeout pour {stream_name}")

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


def get_email_by_full_name(full_name: str) -> str:
    #Récupère l'email à partir du nom complet.
    result = client.get_members()
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
    print(msg)
    content = msg["content"].strip()
    user_email = msg["sender_email"]

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
        if datetime.now(timezone.utc) > obj.end_date and not obj.channels_created:
            # Créer les channels et répartir les utilisateurs
            groups = obj.split_into_groups()
            obj.create_streams_for_groups(groups)
            obj.channels_created = True  # Marquer que les channels ont été créés
            print(f"Channels créés pour l'objet D '{name}'.")
            obj.start_debate_process()  # Démarrer le processus de débat

def message_listener() -> None:
    #Fonction pour écouter les messages entrants.
    print("Démarrage de l'écoute des messages...")
    get_client().call_on_each_message(handle_message)

def create_debat() -> None:
    print("Vérification des débats à créer...")
    for debat in Debat.objects.all():
        if not debat.debat_created:
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
        #print(client.get_members())
        
        i+=1

if __name__ == "__main__":
    threading.Thread(target=message_listener, daemon=True).start()
    threading.Thread(target=event_listener, daemon=True).start()
    main_loop()
