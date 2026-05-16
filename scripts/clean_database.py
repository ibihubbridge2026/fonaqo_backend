#!/usr/bin/env python3
"""
Script de nettoyage complet de la base de données FONACO
Ce script vide toutes les tables de la base de données tout en préservant la structure
Utilisation: python manage.py shell < scripts/clean_database.py
"""

import os
import sys
import django

# Configuration de l'environnement Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from django.core.management import call_command
from django.apps import apps

def truncate_all_tables():
    """Vide toutes les tables de la base de données"""
    print("🗑️  DÉBUT DU NETTOYAGE COMPLET DE LA BASE DE DONNÉES...")
    
    # Liste des modèles à vider dans l'ordre correct (pour éviter les contraintes de clés étrangères)
    models_to_truncate = [
        # Chat et communications
        ('chat', 'Message'),
        ('chat_enhanced', 'EnhancedMessage'),
        ('chat_enhanced', 'ChatRoom'),
        
        # Litiges et disputes
        ('disputes', 'Dispute'),
        ('disputes', 'DisputeMessage'),
        
        # Missions et opportunités
        ('missions_enhanced', 'EnhancedMission'),
        ('missions', 'MissionApplication'),
        ('missions', 'MissionTracking'),
        ('opportunities', 'Opportunity'),
        
        # Paiements et wallets
        ('payments', 'Transaction'),
        ('payments', 'Payment'),
        ('escrow', 'EscrowTransaction'),
        ('wallets', 'Wallet'),
        ('wallets', 'WalletTransaction'),
        
        # Boosts et IA
        ('boosts', 'Boost'),
        ('boosts', 'BoostPurchase'),
        ('ai_search', 'AISearchQuery'),
        
        # Notifications
        ('notifications', 'Notification'),
        ('notifications', 'PushSubscription'),
        
        # Évaluations et statistiques
        ('statistics', 'UserRating'),
        ('statistics', 'AgentStats'),
        
        # Services
        ('services', 'Service'),
        ('services', 'ServiceCategory'),
        
        # Comptes utilisateurs (garder les modèles de base mais vider les données)
        ('accounts', 'User'),
    ]
    
    try:
        with connection.cursor() as cursor:
            # Désactiver les contraintes de clés étrangères temporairement
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            print("✅ Contraintes de clés étrangères désactivées")
            
            # Vider chaque table
            for app_label, model_name in models_to_truncate:
                try:
                    model = apps.get_model(app_label, model_name)
                    table_name = model._meta.db_table
                    
                    # Vider la table
                    cursor.execute(f"TRUNCATE TABLE {table_name};")
                    print(f"✅ Table {table_name} vidée")
                    
                except Exception as e:
                    print(f"⚠️  Erreur lors du vidage de {app_label}.{model_name}: {e}")
                    continue
            
            # Réactiver les contraintes de clés étrangères
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            print("✅ Contraintes de clés étrangères réactivées")
            
            # Réinitialiser les auto-incréments
            auto_increment_tables = [
                'accounts_user',
                'chat_message',
                'missions_mission',
                'payments_transaction',
                'wallets_wallettransaction',
                'notifications_notification',
                'disputes_dispute',
            ]
            
            for table_name in auto_increment_tables:
                try:
                    cursor.execute(f"ALTER TABLE {table_name} AUTO_INCREMENT = 1;")
                    print(f"✅ Auto-incrément réinitialisé pour {table_name}")
                except Exception as e:
                    print(f"⚠️  Erreur lors de la réinitialisation de {table_name}: {e}")
            
        connection.commit()
        print("🎉 NETTOYAGE COMPLET TERMINÉ AVEC SUCCÈS!")
        
    except Exception as e:
        print(f"❌ Erreur lors du nettoyage: {e}")
        connection.rollback()
        raise

def reset_sequences():
    """Réinitialise les séquences PostgreSQL si nécessaire"""
    try:
        with connection.cursor() as cursor:
            # Pour PostgreSQL, réinitialiser toutes les séquences
            cursor.execute("""
                SELECT sequence_name 
                FROM information_schema.sequences 
                WHERE sequence_schema = 'public'
            """)
            
            sequences = cursor.fetchall()
            
            for sequence, in sequences:
                try:
                    cursor.execute(f"ALTER SEQUENCE {sequence} RESTART WITH 1;")
                    print(f"✅ Séquence {sequence} réinitialisée")
                except Exception as e:
                    print(f"⚠️  Erreur lors de la réinitialisation de la séquence {sequence}: {e}")
        
        connection.commit()
        print("✅ Séquences réinitialisées")
        
    except Exception as e:
        print(f"⚠️  Erreur lors de la réinitialisation des séquences: {e}")

def clear_media_files():
    """Nettoie les fichiers médias"""
    import shutil
    
    media_dirs = [
        'media/avatars/',
        'media/mission_images/',
        'media/chat_media/',
        'media/documents/',
        'media/service_images/',
    ]
    
    for media_dir in media_dirs:
        if os.path.exists(media_dir):
            try:
                shutil.rmtree(media_dir)
                os.makedirs(media_dir, exist_ok=True)
                print(f"✅ Répertoire {media_dir} nettoyé")
            except Exception as e:
                print(f"⚠️  Erreur lors du nettoyage de {media_dir}: {e}")

def run_migrations():
    """Applique les migrations pour s'assurer que la structure est correcte"""
    print("🔄 Application des migrations...")
    try:
        call_command('migrate', verbosity=0)
        print("✅ Migrations appliquées avec succès")
    except Exception as e:
        print(f"❌ Erreur lors des migrations: {e}")
        raise

def main():
    """Fonction principale"""
    print("=" * 60)
    print("🧹 SCRIPT DE NETTOYAGE COMPLET DE LA BASE FONACO")
    print("=" * 60)
    
    # Confirmation de l'utilisateur
    confirm = input("⚠️  CE SCRIPT VA DÉTRUIRE TOUTES LES DONNÉES! Êtes-vous sûr? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Opération annulée")
        return
    
    print("\n🚀 Démarrage du nettoyage...")
    
    try:
        # 1. Vider toutes les tables
        truncate_all_tables()
        
        # 2. Réinitialiser les séquences
        reset_sequences()
        
        # 3. Nettoyer les fichiers médias
        clear_media_files()
        
        # 4. Appliquer les migrations
        run_migrations()
        
        print("\n" + "=" * 60)
        print("🎉 NETTOYAGE TERMINÉ AVEC SUCCÈS!")
        print("📊 La base de données est maintenant prête pour le seeding")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        print("🔄 Annulation des transactions...")
        sys.exit(1)

if __name__ == "__main__":
    main()
