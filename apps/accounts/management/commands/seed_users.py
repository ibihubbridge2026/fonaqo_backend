from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.wallets.models import Wallet

User = get_user_model()

class Command(BaseCommand):
    help = 'Crée des utilisateurs de test pour le développement'

    def handle(self, *args, **kwargs):
        # Suppression des utilisateurs de test existants
        test_phone_numbers = ['0150088210', '0150088211', '0150088212']
        test_users = User.objects.filter(phone_number__in=test_phone_numbers)
        
        # Supprimer d'abord les wallets associés
        Wallet.objects.filter(user__in=test_users).delete()
        # Puis supprimer les utilisateurs
        test_users.delete()

        # Création des utilisateurs de test
        test_users_data = [
            {
                'username': 'client_test',
                'email': 'client@test.com',
                'phone_number': '0150088210',
                'password': 'motdepasse',
                'first_name': 'Test',
                'last_name': 'Client',
                'is_client': True,
                'is_agent': False,
                'is_verified': True,
            },
            {
                'username': 'agent_test',
                'email': 'agent@test.com',
                'phone_number': '0150088211',
                'password': 'motdepasse',
                'first_name': 'Test',
                'last_name': 'Agent',
                'is_client': False,
                'is_agent': True,
                'is_verified': True,
            },
            {
                'username': 'admin_test',
                'email': 'admin@test.com',
                'phone_number': '0150088212',
                'password': 'motdepasse',
                'first_name': 'Admin',
                'last_name': 'Test',
                'is_client': False,
                'is_agent': False,
                'is_verified': True,
                'is_staff': True,
                'is_superuser': True,
            },
        ]

        for user_data in test_users_data:
            phone_number = user_data.pop('phone_number')
            password = user_data.pop('password')
            
            user = User.objects.create_user(
                username=user_data.pop('username'),
                email=user_data.pop('email'),
                password=password,
                phone_number=phone_number,
                **user_data
            )
            
            # Créer un wallet pour chaque utilisateur
            Wallet.objects.get_or_create(user=user, defaults={'balance': 10000.0})
            
            user_type = 'Client' if user_data.get('is_client') else 'Agent' if user_data.get('is_agent') else 'Admin'
            self.stdout.write(
                self.style.SUCCESS(f'Utilisateur créé: {phone_number} ({user_type})')
            )

        self.stdout.write(
            self.style.SUCCESS('Utilisateurs de test créés avec succès !')
        )
        self.stdout.write('\nIdentifiants de test:')
        self.stdout.write('Client: 0150088210 / motdepasse')
        self.stdout.write('Agent: 0150088211 / motdepasse')
        self.stdout.write('Admin: 0150088212 / motdepasse')
