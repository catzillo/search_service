from .views import search_view
from django.urls import path, include

urlpatterns = [
    path('search/', search_view, name='search')
]
