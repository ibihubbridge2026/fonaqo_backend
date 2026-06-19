from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.core.seed import DEFAULT_PASSWORD, run_seed


class Command(BaseCommand):
    help = "Enregistre le compte SuperAdmin unique (option --flush pour vider la base avant)."

    def add_arguments(self, parser):
        parser.add_argument(
            "password",
            nargs="?",
            default=DEFAULT_PASSWORD,
            help="Mot de passe admin (défaut: Fonaco2026!)",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Vide la base avant de seeder (équivalent reset complet des données).",
        )

    def handle(self, *args, **options):
        password = options["password"]
        if options["flush"]:
            self.stdout.write(self.style.WARNING("Vidage de la base de données..."))
            call_command("flush", "--noinput")
            self.stdout.write(self.style.SUCCESS("Base vidée."))

        run_seed(password=password, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Admin enregistré avec succès."))
