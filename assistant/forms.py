# assistant/forms.py
from django import forms

class QuestionForm(forms.Form):
    question = forms.CharField(
        label="",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ask a question..."})
    )
    file = forms.FileField(
        required=False,
        label="",
        widget=forms.ClearableFileInput(attrs={"class": "form-control-file"})
    )
    apply_time = forms.DateTimeField(
        required=False,
        label="Schedule Start",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"})
    )
    revert_time = forms.DateTimeField(
        required=False,
        label="Schedule End",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"})
    )
