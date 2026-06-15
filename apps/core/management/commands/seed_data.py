from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.core.seed import DEFAULT_PASSWORD, run_seed


class Command(BaseCommand):
    help = "Charge les données de démonstration FONAQO (utilisateurs, agents, missions, catégories)."

    def add_arguments(self, parser):
        parser.add_argument(
            "password",
            nargs="?",
            default=DEFAULT_PASSWORD,
            help="Mot de passe commun des comptes de test (défaut: password123)",
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
        self.stdout.write(self.style.SUCCESS("Seed terminé avec succès."))
