from django.core.management.base import BaseCommand
import threading

# Launching Debate Test
from zerver.lib.contrib_bots.Diapyr_bot.Test_debat import main

class Command(BaseCommand):
    help = "Runs the Diapyr Test bot inside the Zulip Django environment"

    def handle(self, *args, **kwargs):
        print("✅ Starting Testing")
        main()
