# audio_processor/serializers.py

from rest_framework import serializers
from .models import Keyword

class KeywordSerializer(serializers.ModelSerializer):
    """
    Serializer for the Keyword model.
    Converts Keyword model instances to JSON and vice-versa.
    """
    class Meta:
        model = Keyword
        fields = '__all__' # Include all fields from the Keyword model
