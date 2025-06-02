from django.core.management.base import BaseCommand
import threading

# Import your bot logic from your existing Diapyr_bot.py
from zerver.lib.contrib_bots.Diapyr_bot.Diapyr_bot import message_listener, main_loop

class Command(BaseCommand):
    help = "Runs the Diapyr bot inside the Zulip Django environment"

    def handle(self, *args, **kwargs):
        print("✅ Starting Diapyr Bot from Django management command.")
        threading.Thread(target=message_listener).start()
        main_loop()

