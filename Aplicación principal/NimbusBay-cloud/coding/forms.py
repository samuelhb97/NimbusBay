from django import forms

class formulario(forms.Form):
    texto = forms.CharField(widget=forms.Textarea({
        'style': 'width: 95%; height: 750px; padding: 10px; border-radius: 5px; border: 1px solid #ccc; resize: both;'
    }), required=True,)
    texto_consola = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['texto'].widget.attrs.update({'id': 'documento'})



