# audio_processor/admin.py

from django.contrib import admin
from .models import Keyword, Transcription

@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ('word', 'is_active', 'created_at', 'updated_at')
    search_fields = ('word', 'talking_point')
    list_filter = ('is_active',)

@admin.register(Transcription)
class TranscriptionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'speaker_type', 'text', 'timestamp')
    search_fields = ('session_id', 'text')
    list_filter = ('speaker_type',)
    readonly_fields = ('session_id', 'speaker_type', 'text', 'timestamp') # Make fields read-only
