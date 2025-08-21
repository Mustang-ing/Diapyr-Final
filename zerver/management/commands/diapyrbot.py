from django.core.management.base import BaseCommand
import threading

# Import your bot logic from your existing Diapyr_bot.py
from zerver.lib.contrib_bots.Diapyr_bot.Diapyr_bot import  message_listener, main_loop
from zerver.lib.diapyr import main_db


#Mode d'exécution 
#1 - Mode classique : Diapyr_bot
#2 - Mode avec la base de donné : lib/diapyr.py
EXECUTION_MODE = 2

class Command(BaseCommand):
    help = "Runs the Diapyr bot inside the Zulip Django environment"

    def handle(self, *args, **kwargs):
        print("✅ Starting Diapyr Bot from Django management command.")
        if EXECUTION_MODE == 1:
            print("Starting in classic bot mode (EXECUTION_MODE=1)")
            main_loop()
        elif EXECUTION_MODE == 2:
            print("Starting in DB-backed mode (EXECUTION_MODE=2)")
            main_db()
        else:
            print(f"Unknown EXECUTION_MODE={EXECUTION_MODE}; nothing started.")

