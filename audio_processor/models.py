# audio_processor/models.py

from django.db import models

class Keyword(models.Model):
    """
    Represents a keyword to be detected in prospect speech.
    """
    word = models.CharField(max_length=100, unique=True, help_text="The keyword to detect.")
    talking_point = models.TextField(
        blank=True,
        help_text="Optional talking point or suggestion associated with this keyword."
    )
    is_active = models.BooleanField(default=True, help_text="Whether this keyword is currently active for detection.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Keyword"
        verbose_name_plural = "Keywords"
        ordering = ['word']

    def __str__(self):
        return self.word

class Transcription(models.Model):
    """
    Stores transcription results, primarily for historical reference if needed.
    """
    session_id = models.CharField(max_length=255, db_index=True, help_text="Identifier for the audio session.")
    speaker_type = models.CharField(
        max_length=50,
        choices=[('prospect', 'Prospect'), ('agent', 'Agent'), ('unknown', 'Unknown')],
        default='unknown',
        help_text="Type of speaker (e.g., prospect, agent)."
    )
    text = models.TextField(help_text="The transcribed text.")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Transcription"
        verbose_name_plural = "Transcriptions"
        ordering = ['timestamp']

    def __str__(self):
        return f"Session {self.session_id} - {self.speaker_type}: {self.text[:50]}..."

