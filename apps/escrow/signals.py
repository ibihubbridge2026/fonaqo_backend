# Les flux escrow sont gérés explicitement via EscrowService dans missions/views.py.
# Pas de verrouillage/libération automatique sur changement de statut pour éviter
# les doubles opérations et les libérations prématurées.
