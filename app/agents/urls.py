from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AgentViewSet, ConversationViewSet

router = DefaultRouter()
router.register(r'agents', AgentViewSet, basename='agent')
router.register(r'conversations', ConversationViewSet, basename='conversation')

urlpatterns = [
    path('', include(router.urls)),
]
