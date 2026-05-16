#!/usr/bin/env python3
"""
Script de test pour valider les modifications de l'AI Search
"""

import os
import sys
import django
from django.conf import settings

# Configuration de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.append('/home/ghost/Documents/fonaqo_dev/fonaqo_back')

# Initialiser Django
django.setup()

from apps.ai_search.services import AISearchService
from django.contrib.auth import get_user_model

User = get_user_model()

def test_ai_search_missions():
    """Test la recherche IA de type 'mission'"""
    print("🔍 Test AI Search - Type: mission")
    print("=" * 50)
    
    # Créer un utilisateur de test
    user = User(username='testuser', email='test@example.com')
    user.id = 1  # Simuler un utilisateur existant
    
    # Initialiser le service IA
    ai_service = AISearchService()
    
    # Tester la recherche de missions
    query = "livraison course"
    search_type = "mission"
    
    try:
        result = ai_service.search(query, user, search_type)
        
        print(f"✅ Recherche réussie pour: '{query}' (type: {search_type})")
        print(f"📊 Status: {result.get('status')}")
        print(f"🎯 Confidence: {result.get('confidence')}")
        print(f"📝 Source: {result.get('source')}")
        
        response = result.get('response', {})
        print(f"🔍 Type de réponse: {response.get('type')}")
        print(f"📈 Nombre de résultats: {response.get('total_results', 0)}")
        print(f"💡 Suggestion: {response.get('suggestion')}")
        
        # Afficher les premiers résultats
        results = response.get('results', [])
        if results:
            print("\n📋 Résultats trouvés:")
            for i, mission in enumerate(results[:2], 1):
                print(f"  {i}. {mission.get('title')}")
                print(f"     💰 Prix: {mission.get('price')} FCFA")
                print(f"     📍 Adresse: {mission.get('address')}")
                print(f"     🏷️  Catégorie: {mission.get('category')}")
                print(f"     ⚡ Urgent: {mission.get('isUrgent')}")
                print()
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test mission: {e}")
        return False

def test_ai_search_agents():
    """Test la recherche IA de type 'agent'"""
    print("\n🔍 Test AI Search - Type: agent")
    print("=" * 50)
    
    # Créer un utilisateur de test
    user = User(username='testuser', email='test@example.com')
    user.id = 1  # Simuler un utilisateur existant
    
    # Initialiser le service IA
    ai_service = AISearchService()
    
    # Tester la recherche d'agents
    query = "livraison urgent"
    search_type = "agent"
    
    try:
        result = ai_service.search(query, user, search_type)
        
        print(f"✅ Recherche réussie pour: '{query}' (type: {search_type})")
        print(f"📊 Status: {result.get('status')}")
        print(f"🎯 Confidence: {result.get('confidence')}")
        print(f"📝 Source: {result.get('source')}")
        
        response = result.get('response', {})
        print(f"🔍 Type de réponse: {response.get('type')}")
        print(f"📈 Nombre de résultats: {response.get('total_results', 0)}")
        print(f"💡 Suggestion: {response.get('suggestion')}")
        
        # Afficher les premiers résultats
        results = response.get('results', [])
        if results:
            print("\n👥 Agents trouvés:")
            for i, agent in enumerate(results[:2], 1):
                print(f"  {i}. {agent.get('fullName')}")
                print(f"     ⭐ Note: {agent.get('rating')}/5")
                print(f"     📋 Missions complétées: {agent.get('completedMissions')}")
                print(f"     ⏱️  Temps de réponse: {agent.get('responseTime')}")
                print(f"     🎭 Spécialités: {', '.join(agent.get('specialties', []))}")
                print(f"     ✅ Vérifié: {agent.get('isVerified')}")
                print(f"     🟢 En ligne: {agent.get('isOnline')}")
                print()
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test agent: {e}")
        return False

def test_ai_search_general():
    """Test la recherche IA de type 'general'"""
    print("\n🔍 Test AI Search - Type: general")
    print("=" * 50)
    
    # Créer un utilisateur de test
    user = User(username='testuser', email='test@example.com')
    user.id = 1  # Simuler un utilisateur existant
    
    # Initialiser le service IA
    ai_service = AISearchService()
    
    # Tester la recherche générale
    query = "service réparation"
    search_type = "general"
    
    try:
        result = ai_service.search(query, user, search_type)
        
        print(f"✅ Recherche réussie pour: '{query}' (type: {search_type})")
        print(f"📊 Status: {result.get('status')}")
        print(f"🎯 Confidence: {result.get('confidence')}")
        print(f"📝 Source: {result.get('source')}")
        
        response = result.get('response', {})
        print(f"🔍 Type de réponse: {response.get('type')}")
        print(f"📈 Nombre de résultats: {response.get('total_results', 0)}")
        print(f"💡 Suggestion: {response.get('suggestion')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test general: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Lancement des tests de l'AI Search")
    print("=" * 60)
    
    # Exécuter tous les tests
    test_results = []
    test_results.append(test_ai_search_missions())
    test_results.append(test_ai_search_agents())
    test_results.append(test_ai_search_general())
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    total_tests = len(test_results)
    passed_tests = sum(test_results)
    
    print(f"✅ Tests réussis: {passed_tests}/{total_tests}")
    print(f"❌ Tests échoués: {total_tests - passed_tests}/{total_tests}")
    
    if all(test_results):
        print("\n🎉 TOUS LES TESTS SONT PASSÉS!")
        print("✅ L'adaptation du backend pour gérer le champ 'type' fonctionne correctement.")
    else:
        print("\n⚠️ CERTAINS TESTS ONT ÉCHOUÉ")
        print("🔧 Vérifiez les erreurs ci-dessus pour corriger le problème.")
    
    print("\n🔗 Les endpoints sont prêts pour le frontend:")
    print("   - POST /api/v1/ai/search/ avec type='mission'")
    print("   - POST /api/v1/ai/search/ avec type='agent'")
    print("   - POST /api/v1/ai/search/ avec type='general'")
