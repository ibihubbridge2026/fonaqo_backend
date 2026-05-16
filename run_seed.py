#!/usr/bin/env python3
"""
Script pour exécuter le seed de base de données
"""

import subprocess
import sys
import os

def run_seed():
    """Exécute le seed de base de données"""
    print("🚀 Lancement du seed de base de données...")
    
    try:
        # Exécuter le seed via docker compose
        result = subprocess.run([
            'docker', 'compose', 'exec', '-T', 'web', 
            'python', 'manage.py', 'shell'
        ], input=open('scripts/seed_database.py', 'r').read(), 
        text=True, capture_output=True, cwd='/home/ghost/Documents/fonaqo_dev/fonaqo_back')
        
        print("📊 Sortie du seed:")
        print(result.stdout)
        
        if result.stderr:
            print("⚠️  Erreurs:")
            print(result.stderr)
            
        if result.returncode == 0:
            print("✅ Seed exécuté avec succès!")
        else:
            print(f"❌ Erreur lors de l'exécution: {result.returncode}")
            
    except Exception as e:
        print(f"❌ Erreur critique: {e}")

if __name__ == "__main__":
    run_seed()
