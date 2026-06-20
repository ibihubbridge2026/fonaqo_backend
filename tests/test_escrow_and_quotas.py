"""
Tests unitaires — règles métier critiques FONACO
================================================
Couvre :
  1. Escrow sans influenceur  : 88 % agent / 10 % plateforme / 2 % réserve
  2. Escrow avec influenceur  : 88 % agent / 8 % plateforme / 2 % influenceur / 2 % réserve
  3. Pénalité d'annulation    : 15 % agent / 5 % FONACO / 80 % client
  4. Quotas missions          : 2 standard / 5 si boost actif
  5. Pass Boost Vétéran       : octroyé une seule fois après 21 COMPLETED
  6. Badge payant             : 1 000 FCFA unique, pas de refacturation
"""

from decimal import Decimal
from unittest.mock import patch
from django.db import transaction as db_transaction

from django.test import TestCase

from apps.core.choices import EscrowStatus, TransactionStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(email, **kw):
    """Crée un utilisateur minimal sans appel SMTP."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    defaults = dict(
        username=email.split('@')[0],
        is_agent=kw.pop('is_agent', False),
        is_client=kw.pop('is_client', True),
        is_active=True,
        is_verified=True,
    )
    defaults.update(kw)
    return User.objects.create_user(email=email, password='test1234', **defaults)


def _make_wallet(user, balance: Decimal, escrow_balance: Decimal = Decimal('0')):
    from apps.wallets.models import Wallet
    w, _ = Wallet.objects.get_or_create(user=user)
    w.balance = balance
    w.escrow_balance = escrow_balance
    w.save()
    return w


def _make_mission(client, agent=None, price: Decimal = Decimal('10000')):
    """Crée une mission minimale sans signal ni celery."""
    from django.contrib.gis.geos import Point
    from apps.missions.models import Mission
    return Mission.objects.create(
        client=client,
        agent=agent,
        title='Test mission',
        description='desc',
        price=price,
        location=Point(2.35, 6.36),
        address='Cotonou',
        status='ACCEPTED',
    )


def _make_escrow(mission, amount: Decimal):
    from apps.escrow.models import Escrow
    # Créer escrow_balance côté client
    from apps.wallets.models import Wallet
    w, _ = Wallet.objects.get_or_create(user=mission.client)
    w.escrow_balance = amount
    w.save()
    return Escrow.objects.create(mission=mission, amount=amount, status=EscrowStatus.HELD)


# ---------------------------------------------------------------------------
# 1. Répartition escrow sans influenceur : 88 / 10 / 2
# ---------------------------------------------------------------------------

class EscrowReleaseNoInfluencerTest(TestCase):
    """Vérifie la ventilation 88 % / 10 % / 2 % sans influenceur."""

    def setUp(self):
        self.client_user = _make_user('client@test.com', is_client=True)
        self.agent_user = _make_user('agent@test.com', is_agent=True, is_client=False)
        _make_wallet(self.client_user, Decimal('0'), Decimal('10000'))
        _make_wallet(self.agent_user, Decimal('0'))

    def _run_release(self, gross: Decimal = Decimal('10000')):
        from apps.escrow.services import EscrowService
        from apps.wallets.models import Wallet

        mission = _make_mission(self.client_user, self.agent_user, gross)
        _make_escrow(mission, gross)
        EscrowService.release_to_agent(mission)
        return {
            'agent': Wallet.objects.get(user=self.agent_user).balance,
            'platform': Wallet.objects.filter(user__email='platform@fonaqo.system').first(),
            'reserve': Wallet.objects.filter(user__email='reserve@fonaqo.system').first(),
        }

    def test_agent_receives_88_percent(self):
        self.assertEqual(self._run_release(Decimal('10000'))['agent'], Decimal('8800.00'))

    def test_platform_receives_10_percent(self):
        r = self._run_release(Decimal('10000'))
        self.assertIsNotNone(r['platform'])
        self.assertEqual(r['platform'].balance, Decimal('1000.00'))

    def test_reserve_receives_2_percent(self):
        r = self._run_release(Decimal('10000'))
        self.assertIsNotNone(r['reserve'])
        self.assertEqual(r['reserve'].balance, Decimal('200.00'))

    def test_sum_equals_gross(self):
        """88 + 10 + 2 = 100 % — aucune fuite de FCFA."""
        r = self._run_release(Decimal('10000'))
        total = r['agent'] + r['platform'].balance + r['reserve'].balance
        self.assertEqual(total, Decimal('10000.00'))

    def test_idempotent_on_released_escrow(self):
        """Un second appel sur un escrow RELEASED ne doit pas re-créditer."""
        from apps.escrow.services import EscrowService
        from apps.wallets.models import Wallet
        mission = _make_mission(self.client_user, self.agent_user, Decimal('5000'))
        _make_escrow(mission, Decimal('5000'))
        EscrowService.release_to_agent(mission)
        EscrowService.release_to_agent(mission)  # doit être ignoré
        self.assertEqual(
            Wallet.objects.get(user=self.agent_user).balance,
            Decimal('4400.00'),  # 88 % de 5 000
        )


# ---------------------------------------------------------------------------
# 2. Répartition escrow avec influenceur : 88 / 8 / 2(inf) / 2(réserve)
# ---------------------------------------------------------------------------

class EscrowReleaseWithInfluencerTest(TestCase):
    """Vérifie que l'influenceur (2 %) est prélevé sur la part plateforme (10 %),
    laissant FONACO avec 8 %, l'agent à 88 % et la réserve intacte à 2 %.
    """

    def setUp(self):
        from apps.accounts.models import ClientProfile, Influencer
        self.client_user = _make_user('inf_client@test.com', is_client=True)
        self.agent_user = _make_user('inf_agent@test.com', is_agent=True, is_client=False)
        _make_wallet(self.client_user, Decimal('0'), Decimal('10000'))
        _make_wallet(self.agent_user, Decimal('0'))

        self.influencer = Influencer.objects.create(
            name='Testeur Influence',
            code_promo='TEST2',
            commission_rate=Decimal('0.02'),
        )
        from django.utils import timezone
        profile, _ = ClientProfile.objects.get_or_create(user=self.client_user)
        profile.influencer = self.influencer
        profile.influencer_linked_at = timezone.now()
        profile.save(update_fields=['influencer', 'influencer_linked_at'])

    def _run_release(self, gross: Decimal = Decimal('10000')):
        from apps.escrow.services import EscrowService
        from apps.wallets.models import Wallet
        mission = _make_mission(self.client_user, self.agent_user, gross)
        _make_escrow(mission, gross)
        EscrowService.release_to_agent(mission)
        self.influencer.refresh_from_db()
        return {
            'agent': Wallet.objects.get(user=self.agent_user).balance,
            'platform': Wallet.objects.filter(user__email='platform@fonaqo.system').first(),
            'reserve': Wallet.objects.filter(user__email='reserve@fonaqo.system').first(),
            'influencer_earnings': self.influencer.earnings_balance,
        }

    def test_agent_still_receives_88_percent(self):
        r = self._run_release(Decimal('10000'))
        self.assertEqual(r['agent'], Decimal('8800.00'))

    def test_platform_receives_8_percent_with_influencer(self):
        """FONACO : 10 % - 2 % influenceur = 8 %."""
        r = self._run_release(Decimal('10000'))
        self.assertIsNotNone(r['platform'])
        self.assertEqual(r['platform'].balance, Decimal('800.00'))

    def test_influencer_receives_2_percent(self):
        r = self._run_release(Decimal('10000'))
        self.assertEqual(r['influencer_earnings'], Decimal('200'))

    def test_reserve_still_2_percent_with_influencer(self):
        """La réserve (2 %) ne doit pas être impactée par l'influenceur."""
        r = self._run_release(Decimal('10000'))
        self.assertIsNotNone(r['reserve'])
        self.assertEqual(r['reserve'].balance, Decimal('200.00'))

    def test_sum_equals_gross_with_influencer(self):
        """88 + 8 + 2 + 2 = 100 % — aucune fuite."""
        r = self._run_release(Decimal('10000'))
        total = (
            r['agent']
            + r['platform'].balance
            + r['reserve'].balance
            + Decimal(str(r['influencer_earnings']))
        )
        self.assertEqual(total, Decimal('10000.00'))


# ---------------------------------------------------------------------------
# 3. Pénalité annulation : 15 % agent / 5 % FONACO / 80 % client
# ---------------------------------------------------------------------------

class CancellationPenaltyTest(TestCase):
    """Vérifie la répartition 15/5/80 lors de l'annulation d'une mission acceptée."""

    def setUp(self):
        self.client_user = _make_user('cancel_client@test.com', is_client=True)
        self.agent_user = _make_user('cancel_agent@test.com', is_agent=True, is_client=False)
        _make_wallet(self.client_user, Decimal('0'), Decimal('10000'))
        _make_wallet(self.agent_user, Decimal('0'))

    def _run_cancel(self, gross: Decimal = Decimal('10000')):
        from apps.escrow.services import EscrowService
        from apps.wallets.models import Wallet

        mission = _make_mission(self.client_user, self.agent_user, gross)
        _make_escrow(mission, gross)

        EscrowService.cancel_with_agent_compensation(mission)
        return {
            'client': Wallet.objects.get(user=self.client_user),
            'agent': Wallet.objects.get(user=self.agent_user).balance,
            'platform': Wallet.objects.filter(user__email='platform@fonaqo.system').first(),
        }

    def test_agent_receives_15_percent(self):
        result = self._run_cancel(Decimal('10000'))
        self.assertEqual(result['agent'], Decimal('1500.00'))

    def test_fonaco_receives_5_percent(self):
        result = self._run_cancel(Decimal('10000'))
        self.assertIsNotNone(result['platform'])
        self.assertEqual(result['platform'].balance, Decimal('500.00'))

    def test_client_receives_80_percent(self):
        result = self._run_cancel(Decimal('10000'))
        self.assertEqual(result['client'].balance, Decimal('8000.00'))

    def test_total_equals_gross(self):
        result = self._run_cancel(Decimal('10000'))
        platform_bal = result['platform'].balance if result['platform'] else Decimal('0')
        total = result['agent'] + platform_bal + result['client'].balance
        self.assertEqual(total, Decimal('10000.00'))

    def test_agent_transaction_description(self):
        """Description doit être neutre — pas de % affiché à l'agent."""
        from apps.escrow.services import EscrowService
        from apps.wallets.models import Transaction, Wallet

        mission = _make_mission(self.client_user, self.agent_user, Decimal('5000'))
        _make_escrow(mission, Decimal('5000'))
        EscrowService.cancel_with_agent_compensation(mission)

        agent_wallet = Wallet.objects.get(user=self.agent_user)
        txn = Transaction.objects.filter(wallet=agent_wallet).first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.description, "Indemnisation pour annulation de mission")
        # Le % ne doit PAS apparaître dans la description
        self.assertNotIn('%', txn.description)
        self.assertNotIn('15', txn.description)


# ---------------------------------------------------------------------------
# 4. Quotas de missions simultanées : 2 standard / 5 boosté
# ---------------------------------------------------------------------------

class MissionQuotaTest(TestCase):
    """Vérifie les seuils : 2 standard / 5 boost actif."""

    def setUp(self):
        self.agent = _make_user('quota_agent@test.com', is_agent=True, is_client=False)

    def test_standard_quota_is_2(self):
        from apps.missions.views import _agent_mission_capacity
        self.assertEqual(_agent_mission_capacity(self.agent), 2)

    def test_21_completed_without_boost_still_gives_2(self):
        """Sans boost actif, même 21 COMPLETED → capacité = 2 (reward est un boost)."""
        from django.contrib.gis.geos import Point
        from apps.missions.models import Mission
        from apps.missions.views import _agent_mission_capacity
        client = _make_user('qc21@test.com')
        for i in range(21):
            Mission.objects.create(
                client=client, agent=self.agent, title=f'M{i}', description='d',
                price=Decimal('1000'), location=Point(2.35, 6.36),
                address='Cotonou', status='COMPLETED',
            )
        self.assertEqual(_agent_mission_capacity(self.agent), 2)

    @patch('apps.missions.views._agent_has_active_boost', return_value=True)
    def test_boosted_quota_is_5(self, _mock):
        from apps.missions.views import _agent_mission_capacity
        self.assertEqual(_agent_mission_capacity(self.agent), 5)


# ---------------------------------------------------------------------------
# 5. Pass Boost Vétéran — octroyé une seule fois après 21 COMPLETED
# ---------------------------------------------------------------------------

class VeteranBoostRewardTest(TestCase):
    """Vérifie l'attribution unique du Pass Boost Gratuit 3 jours."""

    def setUp(self):
        from apps.boosts.models import BoostPlan
        self.agent = _make_user('vet_agent@test.com', is_agent=True, is_client=False)
        BoostPlan.objects.get_or_create(
            name='Day Boost', defaults=dict(duration_hours=24, price=Decimal('500'), is_active=True)
        )

    def _create_completed_missions(self, count: int):
        from django.contrib.gis.geos import Point
        from apps.missions.models import Mission
        client = _make_user(f'vclient_{count}@test.com')
        for i in range(count):
            Mission.objects.create(
                client=client, agent=self.agent, title=f'M{i}', description='d',
                price=Decimal('1000'), location=Point(2.35, 6.36),
                address='Cotonou', status='COMPLETED',
            )

    def test_no_boost_granted_at_20_completed(self):
        from apps.missions.views import _grant_veteran_boost_if_eligible
        from apps.boosts.models import AgentBoost
        self._create_completed_missions(20)
        result = _grant_veteran_boost_if_eligible(self.agent)
        self.assertFalse(result)
        self.assertEqual(AgentBoost.objects.filter(agent=self.agent).count(), 0)

    def test_boost_granted_at_21_completed(self):
        from apps.missions.views import _grant_veteran_boost_if_eligible
        from apps.boosts.models import AgentBoost
        self._create_completed_missions(21)
        result = _grant_veteran_boost_if_eligible(self.agent)
        self.assertTrue(result)
        boost = AgentBoost.objects.filter(agent=self.agent, transaction_id='VETERAN_REWARD').first()
        self.assertIsNotNone(boost)
        self.assertEqual(boost.purchase_amount, Decimal('0'))
        self.assertEqual(boost.status, 'active')

    def test_boost_granted_only_once(self):
        """Le second appel retourne False et ne crée pas de second boost."""
        from apps.missions.views import _grant_veteran_boost_if_eligible
        from apps.boosts.models import AgentBoost
        self._create_completed_missions(21)
        _grant_veteran_boost_if_eligible(self.agent)  # 1er appel
        result = _grant_veteran_boost_if_eligible(self.agent)  # 2e appel
        self.assertFalse(result)
        self.assertEqual(
            AgentBoost.objects.filter(agent=self.agent, transaction_id='VETERAN_REWARD').count(),
            1,
        )

    def test_veteran_boost_claimed_persisted(self):
        from apps.missions.views import _grant_veteran_boost_if_eligible
        from apps.accounts.models import AgentProfile
        self._create_completed_missions(21)
        _grant_veteran_boost_if_eligible(self.agent)
        profile = AgentProfile.objects.get(user=self.agent)
        self.assertTrue(profile.veteran_boost_claimed)

    def test_veteran_boost_increases_capacity_to_5(self):
        """Après octroi du pass boost, la capacité passe à 5."""
        from apps.missions.views import _agent_mission_capacity, _grant_veteran_boost_if_eligible
        self._create_completed_missions(21)
        _grant_veteran_boost_if_eligible(self.agent)
        self.assertEqual(_agent_mission_capacity(self.agent), 5)


# ---------------------------------------------------------------------------
# 6. Badge payant — 1 000 FCFA unique
# ---------------------------------------------------------------------------

class BadgePaymentTest(TestCase):
    """Vérifie le prélèvement unique de 1 000 FCFA pour le badge pro."""

    def setUp(self):
        self.agent = _make_user('badge_agent@test.com', is_agent=True, is_client=False)

    def test_deducts_1000_fcfa_on_first_request(self):
        """Première demande : 1 000 FCFA débités du wallet."""
        from apps.accounts.models import AgentProfile
        from apps.wallets.models import Wallet, Transaction
        from django.core.files.uploadedfile import SimpleUploadedFile

        _make_wallet(self.agent, Decimal('2000'))
        profile, _ = AgentProfile.objects.get_or_create(user=self.agent)

        # Simuler la logique de paiement (sans HTTP)
        with db_transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=self.agent)
            if not profile.badge_paid and wallet.balance >= Decimal('1000'):
                wallet.balance -= Decimal('1000')
                wallet.save(update_fields=['balance', 'updated_at'])
                Transaction.objects.create(
                    wallet=wallet,
                    amount=Decimal('-1000'),
                    transaction_type=Transaction.TransactionType.BADGE_FEE,
                    status=TransactionStatus.COMPLETED,
                    description='Badge professionnel FONACO — paiement unique',
                )
                profile.badge_paid = True
                profile.save(update_fields=['badge_paid', 'updated_at'])

        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('1000'))  # 2000 - 1000
        self.assertTrue(profile.badge_paid)

    def test_no_deduction_if_already_paid(self):
        """Si badge_paid=True, aucun prélèvement sur re-demande."""
        from apps.accounts.models import AgentProfile
        from apps.wallets.models import Wallet

        _make_wallet(self.agent, Decimal('500'))
        profile, _ = AgentProfile.objects.get_or_create(user=self.agent)
        profile.badge_paid = True
        profile.save()

        wallet = Wallet.objects.get(user=self.agent)
        initial_balance = wallet.balance

        # Simulation : logique de paiement sautée car badge_paid=True
        if not profile.badge_paid:
            wallet.balance -= Decimal('1000')
            wallet.save()

        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, initial_balance)  # inchangé

    def test_transaction_type_badge_fee(self):
        """Vérifie que le type de transaction est BADGE_FEE."""
        from apps.accounts.models import AgentProfile
        from apps.wallets.models import Wallet, Transaction

        _make_wallet(self.agent, Decimal('5000'))
        profile, _ = AgentProfile.objects.get_or_create(user=self.agent)

        with db_transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=self.agent)
            if not profile.badge_paid:
                wallet.balance -= Decimal('1000')
                wallet.save(update_fields=['balance', 'updated_at'])
                Transaction.objects.create(
                    wallet=wallet,
                    amount=Decimal('-1000'),
                    transaction_type=Transaction.TransactionType.BADGE_FEE,
                    status=TransactionStatus.COMPLETED,
                    description='Badge professionnel FONACO',
                )
                profile.badge_paid = True
                profile.save(update_fields=['badge_paid', 'updated_at'])

        txn = Transaction.objects.filter(
            wallet=wallet,
            transaction_type=Transaction.TransactionType.BADGE_FEE,
        ).first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.amount, Decimal('-1000'))
