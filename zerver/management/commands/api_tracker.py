from django.core.management.base import BaseCommand

# Import your bot logic from your existing Diapyr_bot.py
from zerver.lib.api_call_tracker import  api_tracker


class Command(BaseCommand):
    help = "Check the remaining Zulip API call left"

    def handle(self, *args, **kwargs):
        print("✅ Starting API Tracker from Django management command.")
        api_tracker()

