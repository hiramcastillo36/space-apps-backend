from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AgentViewSet, ConversationViewSet, EventViewSet

router = DefaultRouter()
router.register(r'agents', AgentViewSet, basename='agent')
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'events', EventViewSet, basename='event')

urlpatterns = [
    path('', include(router.urls)),
]
