# assistant/forms.py

from django import forms

class QuestionForm(forms.Form):
    question = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ask a question...",
            }
        )
    )
    file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control-file"})
    )
