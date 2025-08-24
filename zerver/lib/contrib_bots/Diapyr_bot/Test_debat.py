import django,os,sys


#Old way to set the project root from zerver/lib/contrib_bots/Diapyr_bot/Test_debat.py
""""
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(PROJECT_ROOT)
"""
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
django.setup()
import zulip
from datetime import datetime, timedelta
from zerver.models.debat import Debat,Participant
from zerver.models import UserProfile
#from zerver.lib.actions import do_delete_stream
import time

def _parse_cli_args() -> tuple[int | None, int | None, int | None, int | None]:
    """Parse 4 positional CLI args if present: nb_subscribers max_per_group time_between_steps mode.
    Returns a tuple of ints or Nones when not provided.
    """
    args = sys.argv[1:]
    if len(args) >= 4:
        try:
            nb = int(args[0])
            mpg = int(args[1])
            tbs = int(args[2])
            mode = int(args[3])
            return nb, mpg, tbs, mode
        except ValueError:
            # If parsing fails, fall back to interactive
            return None, None, None, None
    return None, None, None, None


def _prompt_params() -> tuple[int, int, int, int]:
    """Interactive prompts (original behavior)."""
    print("Script de test choisiser vos parametres")
    nb_subscribers = int(input("Nombre de participants : "))
    max_per_group = int(input("Nombre de participants maximal dans un groupe : " ))
    time_between_steps = int(input("Temps entre chaque étape (en minutes) : "))
    mode = int(input("Mode de test (1: Rapide, 2: Pré-inscription) : "))
    return nb_subscribers, max_per_group, time_between_steps, mode


def main(nb_subscribers: int | None = None,
         max_per_group: int | None = None,
         time_between_steps: int | None = None,
         mode: int | None = None):
    # Initialize the Zulip client
    client = zulip.Client(config_file="zerver/lib/contrib_bots/Diapyr_bot/zuliprc.txt")

    total = 0
    real_user = []
    # Count the number of users in the Zulip organization
    members = client.get_members()["members"]
    for user in members:
        if not bool(user["is_bot"]):
            total += 1
            real_user.append(user)

    print(f"Nombre total d'utilisateurs dans l'organisation : {total}")

    # Determine parameters: prefer function args, then CLI args, else interactive
    if None in (nb_subscribers, max_per_group, time_between_steps, mode):
        cli_vals = _parse_cli_args()
        if all(v is not None for v in cli_vals):
            nb_subscribers, max_per_group, time_between_steps, mode = cli_vals  # type: ignore[misc]
        else:
            nb_subscribers, max_per_group, time_between_steps, mode = _prompt_params()

    # Validate participants count against available users
    if nb_subscribers is None or max_per_group is None or time_between_steps is None or mode is None:
        print("Paramètres invalides. Veuillez fournir 4 entiers (nb_subscribers max_per_group time_between_steps mode) ou utiliser le mode interactif.")
        exit(1)

    if nb_subscribers > total:
        print("Le nombre de participants est supérieur au nombre de personne dans l'organisation")
        exit(1)

    # Create a new debate
    num = Debat.objects.count()
    debat = Debat.objects.create(
        title=f"TestDebate - Beta3 {num} ",
        creator=UserProfile.objects.get(id=157),  # Assuming the creator is the first user
        max_per_group=max_per_group,
        max_representant=3,
        subscription_end_date=(datetime.now() + timedelta(seconds=1)).isoformat(),
        time_between_round=timedelta(seconds=int(time_between_steps)),
        start_date=(datetime.now() + (timedelta(minutes=30) if mode == 2 else timedelta(seconds=1))).isoformat(),  # Set start date to 30 minutes later for pre-registration mode
        step=(1 if mode == 2 else 1),  # Step 1 for pre-registration mode, Step 2 for quick mode
        description="This is a test debate",
    )

    print(f"Débat créé : {debat.title}")

    # Create participants
    for i, user in zip(range(nb_subscribers), real_user):
        debat.debat_participants.add(UserProfile.objects.get(id=user['user_id']))  # Add the user directly to the debate
        print(f"Participant {i+1} créé : {user['full_name']} - {user['email']}")

    # Get the status
    while debat.is_archived is False:
        debat.refresh_from_db()
        print(f"Débat {debat.title} - Étape {debat.step} - Participants : {debat.debat_participant.count()}")

        # Wait for the next step
        time.sleep(time_between_steps)

if __name__ == "__main__":
    main()
   


