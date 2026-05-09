from rest_framework import generics, permissions
from .serializers import FCMDeviceSerializer

class RegisterDeviceView(generics.CreateAPIView):
    serializer_class = FCMDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]