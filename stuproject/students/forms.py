from django import forms
from .models import Fee

class FeeForm(forms.ModelForm):
    class Meta:
        model = Fee
        fields = ['student', 'amount', 'due_date', 'is_paid']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }