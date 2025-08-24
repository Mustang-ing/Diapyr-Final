from django.core.management.base import BaseCommand
import threading

# Launching Debate Test
from zerver.lib.contrib_bots.Diapyr_bot.Test_debat import main

class Command(BaseCommand):
    help = "Runs the Diapyr Test bot inside the Zulip Django environment"

    def add_arguments(self, parser):
        # 4 optional positional args: nb_subscribers max_per_group time_between_steps mode
        parser.add_argument('nb_subscribers', type=int, nargs='?', help='Number of participants')
        parser.add_argument('max_per_group', type=int, nargs='?', help='Max participants per group')
        parser.add_argument('time_between_steps', type=int, nargs='?', help='Time between steps (minutes as per prompt)')
        parser.add_argument('mode', type=int, nargs='?', help='Test mode (1: Rapide, 2: Pré-inscription)')

    def handle(self, *args, **kwargs):
        print("✅ Starting Testing")
        main(
            kwargs.get('nb_subscribers'),
            kwargs.get('max_per_group'),
            kwargs.get('time_between_steps'),
            kwargs.get('mode'),
        )
